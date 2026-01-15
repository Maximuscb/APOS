# backend/app/routes/counts.py
"""
Phase 11: Physical inventory count API routes.
"""
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.decorators import require_auth, require_permission
from app.services import count_service
from app.models import Count


counts_bp = Blueprint("counts", __name__, url_prefix="/api/counts")


@counts_bp.route("", methods=["POST"])
@require_auth
@require_permission("CREATE_COUNTS")
def create_count():
    """
    Create a new count document.

    Request body:
    {
        "store_id": int,
        "count_type": str,  // "CYCLE" or "FULL"
        "reason": str (optional)
    }

    Returns:
        201: Count created
        400: Invalid request
        403: Forbidden
    """
    data = request.get_json()

    try:
        count = count_service.create_count(
            store_id=data["store_id"],
            count_type=data["count_type"],
            user_id=request.user_id,
            reason=data.get("reason"),
        )

        db.session.commit()

        return jsonify(count.to_dict()), 201

    except KeyError as e:
        db.session.rollback()
        return jsonify({"error": f"Missing required field: {e}"}), 400
    except count_service.CountError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@counts_bp.route("/<int:count_id>/lines", methods=["POST"])
@require_auth
@require_permission("CREATE_COUNTS")
def add_count_line(count_id: int):
    """
    Add a line item to a count.
    Expected quantity is fetched automatically from system.

    Request body:
    {
        "product_id": int,
        "actual_quantity": int
    }

    Returns:
        201: Line added
        400: Invalid request
        403: Forbidden
        404: Count not found
    """
    data = request.get_json()

    try:
        line = count_service.add_count_line(
            count_id=count_id,
            product_id=data["product_id"],
            actual_quantity=data["actual_quantity"],
        )

        db.session.commit()

        return jsonify(line.to_dict()), 201

    except KeyError as e:
        db.session.rollback()
        return jsonify({"error": f"Missing required field: {e}"}), 400
    except count_service.CountError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@counts_bp.route("/<int:count_id>/approve", methods=["POST"])
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def approve_count(count_id: int):
    """
    Approve a count (manager action).
    Calculates total variances.

    Returns:
        200: Count approved
        400: Invalid state
        403: Forbidden
        404: Count not found
    """
    try:
        count = count_service.approve_count(
            count_id=count_id,
            user_id=request.user_id,
        )

        db.session.commit()

        return jsonify(count.to_dict()), 200

    except count_service.CountError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@counts_bp.route("/<int:count_id>/post", methods=["POST"])
@require_auth
@require_permission("POST_DOCUMENTS")
def post_count(count_id: int):
    """
    Post a count: create ADJUST transactions for variances.

    Returns:
        200: Count posted
        400: Invalid state
        403: Forbidden
        404: Count not found
    """
    try:
        count = count_service.post_count(
            count_id=count_id,
            user_id=request.user_id,
        )

        db.session.commit()

        return jsonify(count.to_dict()), 200

    except count_service.CountError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@counts_bp.route("/<int:count_id>/cancel", methods=["POST"])
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def cancel_count(count_id: int):
    """
    Cancel a count before posting.

    Request body:
    {
        "reason": str
    }

    Returns:
        200: Count cancelled
        400: Invalid state or missing reason
        403: Forbidden
        404: Count not found
    """
    data = request.get_json()

    try:
        reason = data.get("reason")
        if not reason:
            return jsonify({"error": "Cancellation reason is required"}), 400

        count = count_service.cancel_count(
            count_id=count_id,
            user_id=request.user_id,
            reason=reason,
        )

        db.session.commit()

        return jsonify(count.to_dict()), 200

    except count_service.CountError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@counts_bp.route("/<int:count_id>", methods=["GET"])
@require_auth
@require_permission("VIEW_DOCUMENTS")
def get_count(count_id: int):
    """
    Get count summary with lines and variances.

    Returns:
        200: Count summary
        404: Count not found
    """
    try:
        summary = count_service.get_count_summary(count_id)
        return jsonify(summary), 200

    except count_service.CountError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@counts_bp.route("/pending", methods=["GET"])
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def list_pending_counts():
    """
    List pending counts awaiting approval (manager queue).

    Returns:
        200: List of pending counts
    """
    try:
        counts = db.session.query(Count).filter_by(
            status="PENDING"
        ).order_by(Count.created_at.desc()).all()

        return jsonify([c.to_dict() for c in counts]), 200

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@counts_bp.route("", methods=["GET"])
@require_auth
@require_permission("VIEW_DOCUMENTS")
def list_counts():
    """
    List counts with optional filters.

    Query parameters:
        status: Filter by status (PENDING, APPROVED, POSTED, CANCELLED)
        count_type: Filter by type (CYCLE, FULL)
        store_id: Filter by store
        limit: Max results (default 100)

    Returns:
        200: List of counts
    """
    try:
        query = db.session.query(Count)

        # Apply filters
        if status := request.args.get("status"):
            query = query.filter_by(status=status)

        if count_type := request.args.get("count_type"):
            query = query.filter_by(count_type=count_type)

        if store_id := request.args.get("store_id"):
            query = query.filter_by(store_id=int(store_id))

        # Limit results
        limit = int(request.args.get("limit", 100))
        query = query.order_by(Count.created_at.desc()).limit(limit)

        counts = query.all()

        return jsonify([c.to_dict() for c in counts]), 200

    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500
