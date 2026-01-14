# backend/app/routes/lifecycle.py
"""
APOS Phase 5: Document Lifecycle API Routes

These routes handle state transitions for inventory transactions:
- POST /api/lifecycle/approve/:id - Approve a DRAFT transaction (DRAFT → APPROVED)
- POST /api/lifecycle/post/:id - Post an APPROVED transaction (APPROVED → POSTED)
- GET /api/lifecycle/pending - List DRAFT transactions needing approval
- GET /api/lifecycle/approved - List APPROVED transactions ready to post

WHY SEPARATE ROUTES:
- Lifecycle operations are distinct from business operations (receive, adjust, sell)
- Makes it clear which endpoints affect document state vs. creating new documents
- Enables easy authorization rules (e.g., only managers can approve/post)

DESIGN NOTES:
- These routes will require user authentication once Phase 4 (Auth) is implemented
- For now, approved_by_user_id and posted_by_user_id are nullable
- Bulk operations (approve/post multiple) are stubbed for future implementation
"""

from flask import Blueprint, request, jsonify

from ..models import InventoryTransaction
from ..services import lifecycle_service
from ..services.lifecycle_service import LifecycleError
from ..validation import ValidationError


lifecycle_bp = Blueprint("lifecycle", __name__, url_prefix="/api/lifecycle")


@lifecycle_bp.post("/approve/<int:transaction_id>")
def approve_transaction_route(transaction_id: int):
    """
    Approve a DRAFT transaction (DRAFT → APPROVED).

    WHY: Review workflow - data entry creates DRAFT, manager approves it.

    Request body (optional):
        {
            "approved_by_user_id": <int>  // Future: once User model exists
        }

    Response:
        {
            "transaction": {...}  // Updated transaction with status=APPROVED
        }

    Error responses:
        404: Transaction not found
        400: Transaction not in DRAFT status (lifecycle error)
        400: Invalid state transition
    """
    try:
        # TODO (Phase 4): Extract approved_by_user_id from authenticated session
        # For now, accept from request body (optional)
        data = request.get_json() or {}
        approved_by_user_id = data.get("approved_by_user_id")

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
    except Exception as e:
        # Unexpected error
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@lifecycle_bp.post("/post/<int:transaction_id>")
def post_transaction_route(transaction_id: int):
    """
    Post an APPROVED transaction (APPROVED → POSTED).

    WHY: Finalize approved transaction - makes it affect inventory calculations
    and appends to master ledger.

    CRITICAL: Once POSTED, a transaction becomes immutable. This cannot be undone.
    Incorrect transactions must be corrected with reversal transactions.

    Request body (optional):
        {
            "posted_by_user_id": <int>  // Future: once User model exists
        }

    Response:
        {
            "transaction": {...}  // Updated transaction with status=POSTED
        }

    Error responses:
        404: Transaction not found
        400: Transaction not in APPROVED status (lifecycle error)
        400: Invalid state transition
    """
    try:
        # TODO (Phase 4): Extract posted_by_user_id from authenticated session
        # For now, accept from request body (optional)
        data = request.get_json() or {}
        posted_by_user_id = data.get("posted_by_user_id")

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
    except Exception as e:
        # Unexpected error
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@lifecycle_bp.get("/pending")
def list_pending_transactions_route():
    """
    List DRAFT transactions that need approval.

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
        GET /api/lifecycle/pending?store_id=1
        GET /api/lifecycle/pending?store_id=1&product_id=42&limit=50
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

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@lifecycle_bp.get("/approved")
def list_approved_transactions_route():
    """
    List APPROVED transactions ready to be posted.

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
        GET /api/lifecycle/approved?store_id=1
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

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


# ================================================================================
# FUTURE: Bulk Operations
# ================================================================================
# These are stubs for future implementation. Useful for:
# - End-of-day posting of all approved transactions
# - Manager approving a batch of receiving transactions
# ================================================================================

@lifecycle_bp.post("/approve/batch")
def approve_transactions_batch_route():
    """
    Approve multiple DRAFT transactions at once.

    NOT YET IMPLEMENTED - returns 501 Not Implemented.

    Expected request body:
        {
            "transaction_ids": [1, 2, 3, ...],
            "approved_by_user_id": <int>  // Future
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
def post_transactions_batch_route():
    """
    Post multiple APPROVED transactions at once.

    NOT YET IMPLEMENTED - returns 501 Not Implemented.

    Expected request body:
        {
            "transaction_ids": [1, 2, 3, ...],
            "posted_by_user_id": <int>  // Future
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
