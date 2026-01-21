# Overview: Flask API routes for identifiers operations; parses input and returns JSON responses.

# backend/app/routes/identifiers.py
"""
Identifier API routes

SECURITY: All routes require authentication.
- Lookup operations require VIEW_INVENTORY permission (inventory data shouldn't be public)
- Adding identifiers requires MANAGE_IDENTIFIERS permission
- Deactivating identifiers requires MANAGE_IDENTIFIERS permission
"""

from flask import Blueprint, request, jsonify, current_app

from ..services import identifier_service
from ..services.identifier_service import AmbiguousIdentifierError
from ..decorators import require_auth, require_permission


identifiers_bp = Blueprint("identifiers", __name__, url_prefix="/api/identifiers")


@identifiers_bp.get("/lookup/<value>")
@require_auth
@require_permission("VIEW_INVENTORY")
def lookup_product_route(value: str):
    """
    Lookup product by any identifier.

    Requires VIEW_INVENTORY permission.
    """
    try:
        vendor_id = request.args.get("vendor_id", type=int)
        product = identifier_service.lookup_product(value, vendor_id)

        if not product:
            return jsonify({"error": "Product not found"}), 404

        return jsonify({"product": product.to_dict()}), 200

    except AmbiguousIdentifierError as e:
        products = [m.product.to_dict() for m in e.matches]
        return jsonify({
            "error": str(e),
            "ambiguous": True,
            "products": products,
        }), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to lookup identifier")
        return jsonify({"error": "Internal server error"}), 500


@identifiers_bp.post("/")
@require_auth
@require_permission("MANAGE_IDENTIFIERS")
def add_identifier_route():
    """
    Add identifier to product.

    Requires MANAGE_IDENTIFIERS permission.
    """
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
    except Exception:
        current_app.logger.exception("Failed to add identifier")
        return jsonify({"error": "Internal server error"}), 500


@identifiers_bp.post("/<int:identifier_id>/deactivate")
@require_auth
@require_permission("MANAGE_IDENTIFIERS")
def deactivate_identifier_route(identifier_id: int):
    """
    Deactivate an identifier (soft delete).

    Requires MANAGE_IDENTIFIERS permission.

    WHY: Instead of hard-deleting identifiers, we deactivate them so they
    won't be found in lookups but remain for audit history.
    """
    try:
        identifier = identifier_service.deactivate_identifier(identifier_id)

        if not identifier:
            return jsonify({"error": "Identifier not found"}), 404

        return jsonify({
            "identifier": identifier.to_dict(),
            "message": "Identifier deactivated successfully"
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to deactivate identifier")
        return jsonify({"error": "Internal server error"}), 500


@identifiers_bp.post("/<int:identifier_id>/reactivate")
@require_auth
@require_permission("MANAGE_IDENTIFIERS")
def reactivate_identifier_route(identifier_id: int):
    """
    Reactivate a previously deactivated identifier.

    Requires MANAGE_IDENTIFIERS permission.
    """
    try:
        identifier = identifier_service.reactivate_identifier(identifier_id)

        if not identifier:
            return jsonify({"error": "Identifier not found"}), 404

        return jsonify({
            "identifier": identifier.to_dict(),
            "message": "Identifier reactivated successfully"
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to reactivate identifier")
        return jsonify({"error": "Internal server error"}), 500
