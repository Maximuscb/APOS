# backend/app/routes/identifiers.py
"""Phase 2: Identifier API routes"""

from flask import Blueprint, request, jsonify

from ..services import identifier_service


identifiers_bp = Blueprint("identifiers", __name__, url_prefix="/api/identifiers")


@identifiers_bp.get("/lookup/<value>")
def lookup_product_route(value: str):
    """Lookup product by any identifier."""
    try:
        vendor_id = request.args.get("vendor_id", type=int)
        product = identifier_service.lookup_product(value, vendor_id)

        if not product:
            return jsonify({"error": "Product not found"}), 404

        return jsonify({"product": product.to_dict()}), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@identifiers_bp.post("/")
def add_identifier_route():
    """Add identifier to product."""
    try:
        data = request.get_json()
        product_id = data.get("product_id")
        id_type = data.get("type")
        value = data.get("value")
        vendor_id = data.get("vendor_id")
        is_primary = data.get("is_primary", False)

        if not all([product_id, id_type, value]):
            return jsonify({"error": "product_id, type, and value required"}), 400

        identifier = identifier_service.add_identifier(
            product_id=product_id,
            id_type=id_type,
            value=value,
            vendor_id=vendor_id,
            is_primary=is_primary
        )

        return jsonify({"identifier": identifier.to_dict()}), 201

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
