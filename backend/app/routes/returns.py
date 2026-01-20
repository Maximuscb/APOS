# Overview: Flask API routes for returns operations; parses input and returns JSON responses.

# backend/app/routes/returns.py
"""
Return Processing API Routes

WHY: Enable product returns via REST API with manager approval workflow.

DESIGN:
- Create returns referencing original sale
- Add line items specifying what's being returned
- Manager approval/rejection workflow
- Complete returns to restore inventory and reverse COGS
- Permission-based access control

SECURITY:
- PROCESS_RETURN permission required for creating/viewing returns
- Manager-level permissions required for approve/reject/complete
- All operations logged with user attribution
"""

from flask import Blueprint, request, jsonify, g, current_app

from ..models import Return, ReturnLine
from ..extensions import db
from ..services import return_service
from ..services.return_service import ReturnError
from ..decorators import require_auth, require_permission


returns_bp = Blueprint("returns", __name__, url_prefix="/api/returns")


# =============================================================================
# RETURN CREATION
# =============================================================================

@returns_bp.post("/")
@require_auth
@require_permission("PROCESS_RETURN")
def create_return_route():
    """
    Create a new return document (status: PENDING).

    Requires: PROCESS_RETURN permission
    Available to: admin, manager, cashier

    Request body:
    {
        "original_sale_id": 123,
        "store_id": 1,
        "reason": "Customer not satisfied with product",
        "restocking_fee_cents": 500,  (optional, default: 0)
        "register_id": 1,  (optional)
        "register_session_id": 5  (optional)
    }

    Returns:
        201: Return created with PENDING status
        400: Invalid input
        403: Permission denied
    """
    try:
        data = request.get_json()

        original_sale_id = data.get("original_sale_id")
        store_id = data.get("store_id")
        reason = data.get("reason")
        restocking_fee_cents = data.get("restocking_fee_cents", 0)
        register_id = data.get("register_id")
        register_session_id = data.get("register_session_id")

        if not all([original_sale_id, store_id]):
            return jsonify({"error": "original_sale_id and store_id required"}), 400

        return_doc = return_service.create_return(
            original_sale_id=original_sale_id,
            store_id=store_id,
            user_id=g.current_user.id,
            reason=reason,
            restocking_fee_cents=restocking_fee_cents,
            register_id=register_id,
            register_session_id=register_session_id
        )

        return jsonify({"return": return_doc.to_dict()}), 201

    except ReturnError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to create return")
        return jsonify({"error": "Internal server error"}), 500


@returns_bp.post("/<int:return_id>/lines")
@require_auth
@require_permission("PROCESS_RETURN")
def add_return_line_route(return_id: int):
    """
    Add a line item to a return.

    Requires: PROCESS_RETURN permission
    Available to: admin, manager, cashier

    Request body:
    {
        "original_sale_line_id": 456,
        "quantity": 2
    }

    Returns:
        201: Return line added
        400: Invalid input or quantity exceeds original
    """
    try:
        data = request.get_json()

        original_sale_line_id = data.get("original_sale_line_id")
        quantity = data.get("quantity")

        if not all([original_sale_line_id, quantity]):
            return jsonify({"error": "original_sale_line_id and quantity required"}), 400

        return_line = return_service.add_return_line(
            return_id=return_id,
            original_sale_line_id=original_sale_line_id,
            quantity=quantity
        )

        # Get updated return summary
        summary = return_service.get_return_summary(return_id)

        return jsonify({
            "return_line": return_line.to_dict(),
            "summary": summary
        }), 201

    except ReturnError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to add return line")
        return jsonify({"error": "Internal server error"}), 500


# =============================================================================
# RETURN APPROVAL WORKFLOW
# =============================================================================

@returns_bp.post("/<int:return_id>/approve")
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def approve_return_route(return_id: int):
    """
    Approve a return (manager action).

    Requires: APPROVE_DOCUMENTS permission
    Available to: admin, manager

    WHY: Returns require manager approval before processing.
    Prevents fraudulent returns and gives management oversight.

    Returns:
        200: Return approved (status: APPROVED)
        400: Return not in PENDING status
        403: Permission denied
    """
    try:
        return_doc = return_service.approve_return(
            return_id=return_id,
            manager_user_id=g.current_user.id
        )

        return jsonify({"return": return_doc.to_dict()}), 200

    except ReturnError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to approve return")
        return jsonify({"error": "Internal server error"}), 500


@returns_bp.post("/<int:return_id>/reject")
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def reject_return_route(return_id: int):
    """
    Reject a return (manager action).

    Requires: APPROVE_DOCUMENTS permission
    Available to: admin, manager

    Request body:
    {
        "rejection_reason": "Items damaged, outside return window"
    }

    WHY: Manager may reject returns for various reasons:
    - Items damaged/used
    - No receipt
    - Outside return window
    - Suspected fraud

    Returns:
        200: Return rejected (status: REJECTED)
        400: Invalid input or return not PENDING
    """
    try:
        data = request.get_json()
        rejection_reason = data.get("rejection_reason")

        if not rejection_reason:
            return jsonify({"error": "rejection_reason required"}), 400

        return_doc = return_service.reject_return(
            return_id=return_id,
            manager_user_id=g.current_user.id,
            rejection_reason=rejection_reason
        )

        return jsonify({"return": return_doc.to_dict()}), 200

    except ReturnError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to reject return")
        return jsonify({"error": "Internal server error"}), 500


# =============================================================================
# RETURN COMPLETION (INVENTORY RESTORATION)
# =============================================================================

@returns_bp.post("/<int:return_id>/complete")
@require_auth
@require_permission("POST_DOCUMENTS")
def complete_return_route(return_id: int):
    """
    Complete a return: restore inventory and reverse COGS.

    Requires: POST_DOCUMENTS permission
    Available to: admin, manager

    WHY: This is where the accounting happens:
    1. Restore inventory (create RETURN transactions)
    2. Reverse COGS using ORIGINAL sale cost (not current WAC)
    3. Mark return as COMPLETED

    CRITICAL: COGS reversal credits the original cost from the sale,
    NOT the current weighted average cost. This ensures accurate
    profit/loss tracking.

    Returns:
        200: Return completed (status: COMPLETED), inventory restored
        400: Return not APPROVED
        403: Permission denied
    """
    try:
        return_doc = return_service.complete_return(
            return_id=return_id,
            user_id=g.current_user.id
        )

        # Get full summary with inventory transactions
        summary = return_service.get_return_summary(return_id)

        return jsonify({
            "return": return_doc.to_dict(),
            "summary": summary,
            "message": "Return completed. Inventory restored and COGS reversed."
        }), 200

    except ReturnError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to complete return")
        return jsonify({"error": "Internal server error"}), 500


# =============================================================================
# RETURN QUERIES
# =============================================================================

@returns_bp.get("/<int:return_id>")
@require_auth
@require_permission("PROCESS_RETURN")
def get_return_route(return_id: int):
    """
    Get return details with full summary.

    Requires: PROCESS_RETURN permission
    Available to: admin, manager, cashier

    Returns return with:
    - Return details
    - All return lines
    - Original sale info
    - Total refund amount
    """
    try:
        summary = return_service.get_return_summary(return_id)
        return jsonify(summary), 200

    except ReturnError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to load return summary")
        return jsonify({"error": "Internal server error"}), 500


@returns_bp.get("/sales/<int:sale_id>")
@require_auth
@require_permission("PROCESS_RETURN")
def get_sale_returns_route(sale_id: int):
    """
    Get all returns for a sale.

    Requires: PROCESS_RETURN permission
    Available to: admin, manager, cashier

    WHY: View return history for a specific sale.
    Useful for checking if items have already been returned.
    """
    returns = return_service.get_sale_returns(sale_id)

    return jsonify({
        "sale_id": sale_id,
        "returns": [r.to_dict() for r in returns]
    }), 200


@returns_bp.get("/pending")
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def get_pending_returns_route():
    """
    Get all pending returns awaiting manager approval.

    Requires: APPROVE_DOCUMENTS permission
    Available to: admin, manager

    Query params:
    - store_id: Filter by store (required)

    WHY: Managers need a queue of returns to review and approve/reject.
    """
    store_id = request.args.get("store_id", type=int)

    if not store_id:
        return jsonify({"error": "store_id query parameter required"}), 400

    pending_returns = return_service.get_pending_returns(store_id)

    return jsonify({
        "pending_returns": [r.to_dict() for r in pending_returns]
    }), 200


@returns_bp.get("/")
@require_auth
@require_permission("PROCESS_RETURN")
def list_returns_route():
    """
    List returns with filters.

    Requires: PROCESS_RETURN permission
    Available to: admin, manager, cashier

    Query params:
    - store_id: Filter by store (required)
    - status: Filter by status (PENDING, APPROVED, COMPLETED, REJECTED)
    - limit: Max returns to show (default: 50)

    Returns list of returns sorted by creation date (newest first).
    """
    store_id = request.args.get("store_id", type=int)
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)

    if not store_id:
        return jsonify({"error": "store_id query parameter required"}), 400

    query = db.session.query(Return).filter_by(store_id=store_id)

    if status:
        query = query.filter_by(status=status)

    returns = query.order_by(Return.created_at.desc()).limit(limit).all()

    return jsonify({
        "returns": [r.to_dict() for r in returns]
    }), 200
