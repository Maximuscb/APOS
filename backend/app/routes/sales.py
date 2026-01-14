# backend/app/routes/sales.py
"""Phase 3: Sales API routes"""

from flask import Blueprint, request, jsonify

from ..models import Sale, SaleLine
from ..extensions import db
from ..services import sales_service


sales_bp = Blueprint("sales", __name__, url_prefix="/api/sales")


@sales_bp.post("/")
def create_sale_route():
    """Create new draft sale."""
    try:
        data = request.get_json() or {}
        store_id = data.get("store_id")
        user_id = data.get("user_id")  # Nullable until auth complete

        if not store_id:
            return jsonify({"error": "store_id required"}), 400

        sale = sales_service.create_sale(store_id, user_id)

        return jsonify({"sale": sale.to_dict()}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sales_bp.post("/<int:sale_id>/lines")
def add_line_route(sale_id: int):
    """Add line to sale."""
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
def post_sale_route(sale_id: int):
    """Post sale - creates inventory transactions."""
    try:
        sale = sales_service.post_sale(sale_id)
        return jsonify({"sale": sale.to_dict()}), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sales_bp.get("/<int:sale_id>")
def get_sale_route(sale_id: int):
    """Get sale with lines."""
    sale = db.session.query(Sale).get(sale_id)
    if not sale:
        return jsonify({"error": "Sale not found"}), 404

    lines = db.session.query(SaleLine).filter_by(sale_id=sale_id).all()

    return jsonify({
        "sale": sale.to_dict(),
        "lines": [line.to_dict() for line in lines]
    }), 200
