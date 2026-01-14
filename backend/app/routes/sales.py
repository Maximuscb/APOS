# backend/app/routes/sales.py
"""Phase 7: Sales API routes with permission enforcement"""

from flask import Blueprint, request, jsonify, g

from ..models import Sale, SaleLine
from ..extensions import db
from ..services import sales_service
from ..decorators import require_auth, require_permission


sales_bp = Blueprint("sales", __name__, url_prefix="/api/sales")


@sales_bp.post("/")
@require_auth
@require_permission("CREATE_SALE")
def create_sale_route():
    """
    Create new draft sale.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier
    """
    try:
        data = request.get_json() or {}
        store_id = data.get("store_id")

        if not store_id:
            return jsonify({"error": "store_id required"}), 400

        # Use authenticated user from g.current_user
        sale = sales_service.create_sale(store_id, g.current_user.id)

        return jsonify({"sale": sale.to_dict()}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sales_bp.post("/<int:sale_id>/lines")
@require_auth
@require_permission("CREATE_SALE")
def add_line_route(sale_id: int):
    """
    Add line to sale.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier
    """
    try:
        data = request.get_json()
        product_id = data.get("product_id")
        quantity = data.get("quantity")

        if not all([product_id, quantity]):
            return jsonify({"error": "product_id and quantity required"}), 400

        line = sales_service.add_line(sale_id, product_id, quantity)

        return jsonify({"line": line.to_dict()}), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sales_bp.post("/<int:sale_id>/post")
@require_auth
@require_permission("POST_SALE")
def post_sale_route(sale_id: int):
    """
    Post sale - creates inventory transactions.

    Requires: POST_SALE permission
    Available to: admin, manager, cashier
    """
    try:
        sale = sales_service.post_sale(sale_id)
        return jsonify({"sale": sale.to_dict()}), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sales_bp.get("/<int:sale_id>")
@require_auth
@require_permission("CREATE_SALE")  # Can view sales if can create them
def get_sale_route(sale_id: int):
    """
    Get sale with lines.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier
    """
    sale = db.session.query(Sale).get(sale_id)
    if not sale:
        return jsonify({"error": "Sale not found"}), 404

    lines = db.session.query(SaleLine).filter_by(sale_id=sale_id).all()

    return jsonify({
        "sale": sale.to_dict(),
        "lines": [line.to_dict() for line in lines]
    }), 200
