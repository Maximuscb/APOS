# Overview: Flask API routes for vendor operations; parses input and returns JSON responses.

"""
Vendor Routes

SECURITY: All routes require authentication.
- View operations require VIEW_VENDORS permission
- Create/update/deactivate require MANAGE_VENDORS permission

Vendors are scoped to organizations (multi-tenant).
"""

from flask import Blueprint, request, jsonify, g

from ..decorators import require_auth, require_permission
from ..services import vendor_service
from ..services.vendor_service import VendorNotFoundError, VendorValidationError


vendors_bp = Blueprint("vendors", __name__, url_prefix="/api/vendors")


@vendors_bp.get("")
@require_auth
@require_permission("VIEW_VENDORS")
def list_vendors_route():
    """
    List vendors for the current organization.

    Query parameters:
    - include_inactive: Include inactive vendors (default: false)
    - search: Search term for name, code, or reorder mechanism
    - limit: Maximum results (default: 100)
    - offset: Pagination offset (default: 0)

    Returns:
        {items: Vendor[], count: int, limit: int, offset: int}
    """
    org_id = g.org_id

    include_inactive = request.args.get("include_inactive", "false").lower() == "true"
    search = request.args.get("search")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Clamp limit
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500
    if offset < 0:
        offset = 0

    vendors, total = vendor_service.list_vendors(
        org_id=org_id,
        include_inactive=include_inactive,
        search=search,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "items": [v.to_dict() for v in vendors],
        "count": total,
        "limit": limit,
        "offset": offset,
    })


@vendors_bp.post("")
@require_auth
@require_permission("MANAGE_VENDORS")
def create_vendor_route():
    """
    Create a new vendor.

    Request body:
    {
        "name": "Vendor Name",  // required
        "code": "VCODE",        // optional, unique within org
        "reorder_mechanism": "Send an email", // required
        "contact_name": "...",  // optional
        "contact_email": "...", // optional
        "contact_phone": "...", // optional
        "address": "...",       // optional
        "notes": "..."          // optional
    }

    Returns:
        Created Vendor object
    """
    org_id = g.org_id
    user_id = g.current_user.id

    data = request.get_json(silent=True) or {}

    name = data.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400
    reorder_mechanism = data.get("reorder_mechanism")
    if not reorder_mechanism:
        return jsonify({"error": "reorder_mechanism is required"}), 400

    try:
        vendor = vendor_service.create_vendor(
            org_id=org_id,
            name=name,
            code=data.get("code"),
            contact_name=data.get("contact_name"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            reorder_mechanism=reorder_mechanism,
            address=data.get("address"),
            notes=data.get("notes"),
            created_by_user_id=user_id,
        )
        return jsonify(vendor.to_dict()), 201
    except VendorValidationError as e:
        return jsonify({"error": str(e)}), 400


@vendors_bp.get("/<int:vendor_id>")
@require_auth
@require_permission("VIEW_VENDORS")
def get_vendor_route(vendor_id: int):
    """
    Get a vendor by ID.

    Returns:
        Vendor object
    """
    org_id = g.org_id

    try:
        vendor = vendor_service.get_vendor(vendor_id)
        # Verify vendor belongs to this organization
        if vendor.org_id != org_id:
            return jsonify({"error": "Vendor not found"}), 404
        return jsonify(vendor.to_dict())
    except VendorNotFoundError:
        return jsonify({"error": "Vendor not found"}), 404


@vendors_bp.put("/<int:vendor_id>")
@require_auth
@require_permission("MANAGE_VENDORS")
def update_vendor_route(vendor_id: int):
    """
    Update a vendor.

    Request body (all fields optional):
    {
        "name": "...",
        "code": "...",
        "reorder_mechanism": "...",
        "contact_name": "...",
        "contact_email": "...",
        "contact_phone": "...",
        "address": "...",
        "notes": "..."
    }

    Returns:
        Updated Vendor object
    """
    org_id = g.org_id
    user_id = g.current_user.id

    # First verify the vendor belongs to this org
    try:
        vendor = vendor_service.get_vendor(vendor_id)
        if vendor.org_id != org_id:
            return jsonify({"error": "Vendor not found"}), 404
    except VendorNotFoundError:
        return jsonify({"error": "Vendor not found"}), 404

    data = request.get_json(silent=True) or {}

    try:
        vendor = vendor_service.update_vendor(
            vendor_id=vendor_id,
            name=data.get("name"),
            code=data.get("code"),
            contact_name=data.get("contact_name"),
            contact_email=data.get("contact_email"),
            contact_phone=data.get("contact_phone"),
            reorder_mechanism=data.get("reorder_mechanism"),
            address=data.get("address"),
            notes=data.get("notes"),
            updated_by_user_id=user_id,
        )
        return jsonify(vendor.to_dict())
    except VendorNotFoundError:
        return jsonify({"error": "Vendor not found"}), 404
    except VendorValidationError as e:
        return jsonify({"error": str(e)}), 400


@vendors_bp.delete("/<int:vendor_id>")
@require_auth
@require_permission("MANAGE_VENDORS")
def deactivate_vendor_route(vendor_id: int):
    """
    Deactivate a vendor (soft delete).

    Returns:
        Deactivated Vendor object
    """
    org_id = g.org_id
    user_id = g.current_user.id

    # First verify the vendor belongs to this org
    try:
        vendor = vendor_service.get_vendor(vendor_id)
        if vendor.org_id != org_id:
            return jsonify({"error": "Vendor not found"}), 404
    except VendorNotFoundError:
        return jsonify({"error": "Vendor not found"}), 404

    try:
        vendor = vendor_service.deactivate_vendor(
            vendor_id=vendor_id,
            deactivated_by_user_id=user_id,
        )
        return jsonify(vendor.to_dict())
    except VendorNotFoundError:
        return jsonify({"error": "Vendor not found"}), 404
    except VendorValidationError as e:
        return jsonify({"error": str(e)}), 400


@vendors_bp.post("/<int:vendor_id>/reactivate")
@require_auth
@require_permission("MANAGE_VENDORS")
def reactivate_vendor_route(vendor_id: int):
    """
    Reactivate an inactive vendor.

    Returns:
        Reactivated Vendor object
    """
    org_id = g.org_id
    user_id = g.current_user.id

    # First verify the vendor belongs to this org
    try:
        vendor = vendor_service.get_vendor(vendor_id)
        if vendor.org_id != org_id:
            return jsonify({"error": "Vendor not found"}), 404
    except VendorNotFoundError:
        return jsonify({"error": "Vendor not found"}), 404

    try:
        vendor = vendor_service.reactivate_vendor(
            vendor_id=vendor_id,
            reactivated_by_user_id=user_id,
        )
        return jsonify(vendor.to_dict())
    except VendorNotFoundError:
        return jsonify({"error": "Vendor not found"}), 404
    except VendorValidationError as e:
        return jsonify({"error": str(e)}), 400


@vendors_bp.get("/by-code/<code>")
@require_auth
@require_permission("VIEW_VENDORS")
def get_vendor_by_code_route(code: str):
    """
    Get a vendor by code within the current organization.

    Returns:
        Vendor object
    """
    org_id = g.org_id

    vendor = vendor_service.get_vendor_by_code(org_id, code)
    if not vendor:
        return jsonify({"error": "Vendor not found"}), 404

    return jsonify(vendor.to_dict())
