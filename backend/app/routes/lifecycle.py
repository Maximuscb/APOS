# backend/app/routes/lifecycle.py
"""
APOS Phase 5: Document Lifecycle API Routes

These routes handle state transitions for inventory transactions:
- POST /api/lifecycle/approve/:id - Approve a DRAFT transaction (DRAFT -> APPROVED)
- POST /api/lifecycle/post/:id - Post an APPROVED transaction (APPROVED -> POSTED)
- GET /api/lifecycle/pending - List DRAFT transactions needing approval
- GET /api/lifecycle/approved - List APPROVED transactions ready to post

WHY SEPARATE ROUTES:
- Lifecycle operations are distinct from business operations (receive, adjust, sell)
- Makes it clear which endpoints affect document state vs. creating new documents
- Enables easy authorization rules (e.g., only managers can approve/post)

SECURITY:
- All routes require authentication
- Approve/post operations require APPROVE_DOCUMENTS and POST_DOCUMENTS permissions
- User IDs are taken from the authenticated session (g.current_user), NOT from request body
- This prevents spoofing of the audit trail
"""

from flask import Blueprint, request, jsonify, g, current_app

from ..models import InventoryTransaction
from ..services import lifecycle_service
from ..services.lifecycle_service import LifecycleError
from ..validation import ValidationError
from ..decorators import require_auth, require_permission


lifecycle_bp = Blueprint("lifecycle", __name__, url_prefix="/api/lifecycle")


@lifecycle_bp.post("/approve/<int:transaction_id>")
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def approve_transaction_route(transaction_id: int):
    """
    Approve a DRAFT transaction (DRAFT -> APPROVED).

    Requires APPROVE_DOCUMENTS permission.

    WHY: Review workflow - data entry creates DRAFT, manager approves it.

    SECURITY: approved_by_user_id is taken from the authenticated session,
    NOT from the request body. This prevents audit trail spoofing.

    Response:
        {
            "transaction": {...}  // Updated transaction with status=APPROVED
        }

    Error responses:
        401: Not authenticated
        403: Missing APPROVE_DOCUMENTS permission
        404: Transaction not found
        400: Transaction not in DRAFT status (lifecycle error)
    """
    try:
        # SECURITY: Use authenticated user from session, NOT from request body
        approved_by_user_id = g.current_user.id

        tx = lifecycle_service.approve_transaction(
            transaction_id,
            approved_by_user_id=approved_by_user_id,
        )

        return jsonify({
            "transaction": tx.to_dict(),
            "message": f"Transaction {transaction_id} approved successfully"
        }), 200

    except ValueError as e:
        # Transaction not found
        return jsonify({"error": str(e)}), 404
    except LifecycleError as e:
        # Invalid state transition
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to approve transaction")
        return jsonify({"error": "Internal server error"}), 500


@lifecycle_bp.post("/post/<int:transaction_id>")
@require_auth
@require_permission("POST_DOCUMENTS")
def post_transaction_route(transaction_id: int):
    """
    Post an APPROVED transaction (APPROVED -> POSTED).

    Requires POST_DOCUMENTS permission.

    WHY: Finalize approved transaction - makes it affect inventory calculations
    and appends to master ledger.

    CRITICAL: Once POSTED, a transaction becomes immutable. This cannot be undone.
    Incorrect transactions must be corrected with reversal transactions.

    SECURITY: posted_by_user_id is taken from the authenticated session,
    NOT from the request body. This prevents audit trail spoofing.

    Response:
        {
            "transaction": {...}  // Updated transaction with status=POSTED
        }

    Error responses:
        401: Not authenticated
        403: Missing POST_DOCUMENTS permission
        404: Transaction not found
        400: Transaction not in APPROVED status (lifecycle error)
    """
    try:
        # SECURITY: Use authenticated user from session, NOT from request body
        posted_by_user_id = g.current_user.id

        tx = lifecycle_service.post_transaction(
            transaction_id,
            posted_by_user_id=posted_by_user_id,
        )

        return jsonify({
            "transaction": tx.to_dict(),
            "message": f"Transaction {transaction_id} posted successfully"
        }), 200

    except ValueError as e:
        # Transaction not found
        return jsonify({"error": str(e)}), 404
    except LifecycleError as e:
        # Invalid state transition
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to post transaction")
        return jsonify({"error": "Internal server error"}), 500


@lifecycle_bp.get("/pending")
@require_auth
@require_permission("VIEW_INVENTORY")
def list_pending_transactions_route():
    """
    List DRAFT transactions that need approval.

    Requires VIEW_INVENTORY permission.

    WHY: Manager approval queue - shows what needs to be reviewed.

    Query parameters:
        store_id (required): Store to query
        product_id (optional): Filter by product
        limit (optional): Max results (default 200)

    Response:
        {
            "transactions": [...]  // List of DRAFT transactions
        }

    USAGE EXAMPLE:
        GET /api/lifecycle/pending'store_id=1
        GET /api/lifecycle/pending'store_id=1&product_id=42&limit=50
    """
    try:
        store_id = request.args.get("store_id", type=int)
        if store_id is None:
            return jsonify({"error": "store_id is required"}), 400

        product_id = request.args.get("product_id", type=int)
        limit = request.args.get("limit", type=int, default=200)

        transactions = lifecycle_service.get_transactions_by_status(
            store_id=store_id,
            status="DRAFT",
            product_id=product_id,
            limit=limit,
        )

        return jsonify({
            "transactions": [tx.to_dict() for tx in transactions],
            "count": len(transactions),
        }), 200

    except Exception:
        current_app.logger.exception("Failed to list pending transactions")
        return jsonify({"error": "Internal server error"}), 500


@lifecycle_bp.get("/approved")
@require_auth
@require_permission("VIEW_INVENTORY")
def list_approved_transactions_route():
    """
    List APPROVED transactions ready to be posted.

    Requires VIEW_INVENTORY permission.

    WHY: Shows transactions that have been reviewed and are ready to
    affect inventory. Useful for batch posting workflows.

    Query parameters:
        store_id (required): Store to query
        product_id (optional): Filter by product
        limit (optional): Max results (default 200)

    Response:
        {
            "transactions": [...]  // List of APPROVED transactions
        }

    USAGE EXAMPLE:
        GET /api/lifecycle/approved'store_id=1
    """
    try:
        store_id = request.args.get("store_id", type=int)
        if store_id is None:
            return jsonify({"error": "store_id is required"}), 400

        product_id = request.args.get("product_id", type=int)
        limit = request.args.get("limit", type=int, default=200)

        transactions = lifecycle_service.get_transactions_by_status(
            store_id=store_id,
            status="APPROVED",
            product_id=product_id,
            limit=limit,
        )

        return jsonify({
            "transactions": [tx.to_dict() for tx in transactions],
            "count": len(transactions),
        }), 200

    except Exception:
        current_app.logger.exception("Failed to list approved transactions")
        return jsonify({"error": "Internal server error"}), 500


# ================================================================================
# FUTURE: Bulk Operations
# ================================================================================
# These are stubs for future implementation. Useful for:
# - End-of-day posting of all approved transactions
# - Manager approving a batch of receiving transactions
# ================================================================================

@lifecycle_bp.post("/approve/batch")
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def approve_transactions_batch_route():
    """
    Approve multiple DRAFT transactions at once.

    Requires APPROVE_DOCUMENTS permission.

    NOT YET IMPLEMENTED - returns 501 Not Implemented.

    Expected request body:
        {
            "transaction_ids": [1, 2, 3, ...]
        }

    Expected response:
        {
            "successful": [{...}, {...}],  // Successfully approved
            "failed": [                    // Failed with reasons
                {"id": 1, "error": "..."},
                ...
            ]
        }
    """
    return jsonify({
        "error": "Batch approval not yet implemented",
        "message": "Use individual /approve/<id> endpoint for now"
    }), 501


@lifecycle_bp.post("/post/batch")
@require_auth
@require_permission("POST_DOCUMENTS")
def post_transactions_batch_route():
    """
    Post multiple APPROVED transactions at once.

    Requires POST_DOCUMENTS permission.

    NOT YET IMPLEMENTED - returns 501 Not Implemented.

    Expected request body:
        {
            "transaction_ids": [1, 2, 3, ...]
        }

    Expected response:
        {
            "successful": [{...}, {...}],  // Successfully posted
            "failed": [                    // Failed with reasons
                {"id": 1, "error": "..."},
                ...
            ]
        }
    """
    return jsonify({
        "error": "Batch posting not yet implemented",
        "message": "Use individual /post/<id> endpoint for now"
    }), 501
