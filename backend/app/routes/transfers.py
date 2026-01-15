# backend/app/routes/transfers.py
"""
Phase 11: Inter-store transfer API routes.
"""
from flask import Blueprint, request, jsonify, g
from app.extensions import db
from app.decorators import require_auth, require_permission
from app.services import transfer_service
from app.services.concurrency import commit_with_retry
from app.models import Transfer


transfers_bp = Blueprint("transfers", __name__, url_prefix="/api/transfers")


@transfers_bp.route("", methods=["POST"])
@require_auth
@require_permission("CREATE_TRANSFERS")
def create_transfer():
    """
    Create a new transfer document.

    Request body:
    {
        "from_store_id": int,
        "to_store_id": int,
        "reason": str (optional)
    }

    Returns:
        201: Transfer created
        400: Invalid request
        403: Forbidden
    """
    data = request.get_json()

    try:
        transfer = transfer_service.create_transfer(
            from_store_id=data["from_store_id"],
            to_store_id=data["to_store_id"],
            user_id=g.current_user.id,
            reason=data.get("reason"),
        )

        commit_with_retry()

        return jsonify(transfer.to_dict()), 201

    except KeyError as e:
        db.session.rollback()
        return jsonify({"error": f"Missing required field: {e}"}), 400
    except transfer_service.TransferError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@transfers_bp.route("/<int:transfer_id>/lines", methods=["POST"])
@require_auth
@require_permission("CREATE_TRANSFERS")
def add_transfer_line(transfer_id: int):
    """
    Add a line item to a transfer.

    Request body:
    {
        "product_id": int,
        "quantity": int
    }

    Returns:
        201: Line added
        400: Invalid request
        403: Forbidden
        404: Transfer not found
    """
    data = request.get_json()

    try:
        line = transfer_service.add_transfer_line(
            transfer_id=transfer_id,
            product_id=data["product_id"],
            quantity=data["quantity"],
        )

        commit_with_retry()

        return jsonify(line.to_dict()), 201

    except KeyError as e:
        db.session.rollback()
        return jsonify({"error": f"Missing required field: {e}"}), 400
    except transfer_service.TransferError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@transfers_bp.route("/<int:transfer_id>/approve", methods=["POST"])
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def approve_transfer(transfer_id: int):
    """
    Approve a transfer (manager action).

    Returns:
        200: Transfer approved
        400: Invalid state
        403: Forbidden
        404: Transfer not found
    """
    try:
        transfer = transfer_service.approve_transfer(
            transfer_id=transfer_id,
            user_id=g.current_user.id,
        )

        commit_with_retry()

        return jsonify(transfer.to_dict()), 200

    except transfer_service.TransferError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@transfers_bp.route("/<int:transfer_id>/ship", methods=["POST"])
@require_auth
@require_permission("POST_DOCUMENTS")
def ship_transfer(transfer_id: int):
    """
    Ship a transfer (mark as IN_TRANSIT).
    Creates negative TRANSFER transactions at source store.

    Returns:
        200: Transfer shipped
        400: Invalid state
        403: Forbidden
        404: Transfer not found
    """
    try:
        transfer = transfer_service.ship_transfer(
            transfer_id=transfer_id,
            user_id=g.current_user.id,
        )

        commit_with_retry()

        return jsonify(transfer.to_dict()), 200

    except transfer_service.TransferError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@transfers_bp.route("/<int:transfer_id>/receive", methods=["POST"])
@require_auth
@require_permission("POST_DOCUMENTS")
def receive_transfer(transfer_id: int):
    """
    Receive a transfer at destination store.
    Creates positive TRANSFER transactions at destination.

    Returns:
        200: Transfer received
        400: Invalid state
        403: Forbidden
        404: Transfer not found
    """
    try:
        transfer = transfer_service.receive_transfer(
            transfer_id=transfer_id,
            user_id=g.current_user.id,
        )

        commit_with_retry()

        return jsonify(transfer.to_dict()), 200

    except transfer_service.TransferError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@transfers_bp.route("/<int:transfer_id>/cancel", methods=["POST"])
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def cancel_transfer(transfer_id: int):
    """
    Cancel a transfer before shipping.

    Request body:
    {
        "reason": str
    }

    Returns:
        200: Transfer cancelled
        400: Invalid state or missing reason
        403: Forbidden
        404: Transfer not found
    """
    data = request.get_json()

    try:
        reason = data.get("reason")
        if not reason:
            return jsonify({"error": "Cancellation reason is required"}), 400

        transfer = transfer_service.cancel_transfer(
            transfer_id=transfer_id,
            user_id=g.current_user.id,
            reason=reason,
        )

        commit_with_retry()

        return jsonify(transfer.to_dict()), 200

    except transfer_service.TransferError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@transfers_bp.route("/<int:transfer_id>", methods=["GET"])
@require_auth
@require_permission("VIEW_DOCUMENTS")
def get_transfer(transfer_id: int):
    """
    Get transfer summary with lines.

    Returns:
        200: Transfer summary
        404: Transfer not found
    """
    try:
        summary = transfer_service.get_transfer_summary(transfer_id)
        return jsonify(summary), 200

    except transfer_service.TransferError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@transfers_bp.route("/pending", methods=["GET"])
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def list_pending_transfers():
    """
    List pending transfers awaiting approval (manager queue).

    Returns:
        200: List of pending transfers
    """
    try:
        transfers = db.session.query(Transfer).filter_by(
            status="PENDING"
        ).order_by(Transfer.created_at.desc()).all()

        return jsonify([t.to_dict() for t in transfers]), 200

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@transfers_bp.route("/in-transit", methods=["GET"])
@require_auth
@require_permission("VIEW_DOCUMENTS")
def list_in_transit_transfers():
    """
    List transfers in transit.

    Returns:
        200: List of in-transit transfers
    """
    try:
        transfers = db.session.query(Transfer).filter_by(
            status="IN_TRANSIT"
        ).order_by(Transfer.shipped_at.desc()).all()

        return jsonify([t.to_dict() for t in transfers]), 200

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@transfers_bp.route("", methods=["GET"])
@require_auth
@require_permission("VIEW_DOCUMENTS")
def list_transfers():
    """
    List transfers with optional filters.

    Query parameters:
        status: Filter by status (PENDING, APPROVED, IN_TRANSIT, RECEIVED, CANCELLED)
        from_store_id: Filter by source store
        to_store_id: Filter by destination store
        limit: Max results (default 100)

    Returns:
        200: List of transfers
    """
    try:
        query = db.session.query(Transfer)

        # Apply filters
        if status := request.args.get("status"):
            query = query.filter_by(status=status)

        if from_store_id := request.args.get("from_store_id"):
            query = query.filter_by(from_store_id=int(from_store_id))

        if to_store_id := request.args.get("to_store_id"):
            query = query.filter_by(to_store_id=int(to_store_id))

        # Limit results
        limit = int(request.args.get("limit", 100))
        query = query.order_by(Transfer.created_at.desc()).limit(limit)

        transfers = query.all()

        return jsonify([t.to_dict() for t in transfers]), 200

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500
