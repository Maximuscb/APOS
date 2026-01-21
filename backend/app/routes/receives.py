# Overview: Flask API routes for receive document operations; parses input and returns JSON responses.

"""
Receive Document Routes

SECURITY: All routes require authentication.
- View operations require VIEW_INVENTORY permission
- Create/modify operations require RECEIVE_INVENTORY permission
- Approve operations require APPROVE_DOCUMENTS permission
- Post operations require POST_DOCUMENTS permission

This replaces the old /api/inventory/receive endpoint.
All receives now go through the document-first workflow with required vendor.
"""

from flask import Blueprint, request, jsonify, g

from ..decorators import require_auth, require_permission, require_any_permission
from ..services import receive_service
from ..services.receive_service import (
    ReceiveDocumentNotFoundError,
    ReceiveDocumentValidationError,
    ReceiveDocumentStateError,
    RECEIVE_TYPES,
)
from app.time_utils import parse_iso_datetime


receives_bp = Blueprint("receives", __name__, url_prefix="/api/receives")


@receives_bp.get("")
@require_auth
@require_permission("VIEW_INVENTORY")
def list_receives_route():
    """
    List receive documents for a store.

    Query parameters:
    - store_id: Store ID (required)
    - status: Filter by status (DRAFT, APPROVED, POSTED, CANCELLED)
    - vendor_id: Filter by vendor
    - receive_type: Filter by type (PURCHASE, DONATION, FOUND, TRANSFER_IN, OTHER)
    - from_date: Filter by occurred_at >= from_date (ISO-8601)
    - to_date: Filter by occurred_at <= to_date (ISO-8601)
    - limit: Maximum results (default: 100)
    - offset: Pagination offset (default: 0)

    Returns:
        {items: ReceiveDocument[], count: int}
    """
    store_id = request.args.get("store_id", type=int)
    if not store_id:
        return jsonify({"error": "store_id is required"}), 400

    status = request.args.get("status")
    vendor_id = request.args.get("vendor_id", type=int)
    receive_type = request.args.get("receive_type")
    from_date_str = request.args.get("from_date")
    to_date_str = request.args.get("to_date")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Parse dates
    from_date = None
    to_date = None
    if from_date_str:
        from_date = parse_iso_datetime(from_date_str)
        if from_date is None:
            return jsonify({"error": "Invalid from_date format"}), 400
    if to_date_str:
        to_date = parse_iso_datetime(to_date_str)
        if to_date is None:
            return jsonify({"error": "Invalid to_date format"}), 400

    # Clamp limit
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500
    if offset < 0:
        offset = 0

    docs, total = receive_service.list_receive_documents(
        store_id=store_id,
        status=status,
        vendor_id=vendor_id,
        receive_type=receive_type,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "items": [d.to_dict() for d in docs],
        "count": total,
        "limit": limit,
        "offset": offset,
    })


@receives_bp.post("")
@require_auth
@require_permission("RECEIVE_INVENTORY")
def create_receive_route():
    """
    Create a new receive document.

    Request body:
    {
        "store_id": 1,           // required
        "vendor_id": 1,          // required - every receive needs a vendor
        "receive_type": "PURCHASE",  // required: PURCHASE, DONATION, FOUND, TRANSFER_IN, OTHER
        "occurred_at": "...",    // optional, ISO-8601
        "reference_number": "..", // optional (PO number, invoice, etc.)
        "notes": "..."           // optional
    }

    Returns:
        Created ReceiveDocument object
    """
    user_id = g.current_user.id
    data = request.get_json(silent=True) or {}

    store_id = data.get("store_id")
    vendor_id = data.get("vendor_id")
    receive_type = data.get("receive_type")

    if not store_id:
        return jsonify({"error": "store_id is required"}), 400
    if not vendor_id:
        return jsonify({"error": "vendor_id is required - every receive must have a vendor"}), 400
    if not receive_type:
        return jsonify({"error": f"receive_type is required. Must be one of: {', '.join(RECEIVE_TYPES)}"}), 400

    try:
        doc = receive_service.create_receive_document(
            store_id=store_id,
            vendor_id=vendor_id,
            receive_type=receive_type,
            created_by_user_id=user_id,
            occurred_at=data.get("occurred_at"),
            reference_number=data.get("reference_number"),
            notes=data.get("notes"),
        )
        return jsonify(doc.to_dict()), 201
    except ReceiveDocumentValidationError as e:
        return jsonify({"error": str(e)}), 400


@receives_bp.get("/<int:document_id>")
@require_auth
@require_permission("VIEW_INVENTORY")
def get_receive_route(document_id: int):
    """
    Get a receive document with lines.

    Returns:
        ReceiveDocument with lines array
    """
    try:
        result = receive_service.get_receive_document_with_lines(document_id)
        return jsonify(result)
    except ReceiveDocumentNotFoundError:
        return jsonify({"error": "Receive document not found"}), 404


@receives_bp.post("/<int:document_id>/lines")
@require_auth
@require_permission("RECEIVE_INVENTORY")
def add_line_route(document_id: int):
    """
    Add a line item to a receive document.

    Request body:
    {
        "product_id": 1,         // required
        "quantity": 10,          // required, must be positive
        "unit_cost_cents": 1000, // required
        "note": "..."            // optional
    }

    Returns:
        Created ReceiveDocumentLine object
    """
    data = request.get_json(silent=True) or {}

    product_id = data.get("product_id")
    quantity = data.get("quantity")
    unit_cost_cents = data.get("unit_cost_cents")

    if not product_id:
        return jsonify({"error": "product_id is required"}), 400
    if quantity is None:
        return jsonify({"error": "quantity is required"}), 400
    if unit_cost_cents is None:
        return jsonify({"error": "unit_cost_cents is required"}), 400

    try:
        line = receive_service.add_receive_line(
            document_id=document_id,
            product_id=product_id,
            quantity=quantity,
            unit_cost_cents=unit_cost_cents,
            note=data.get("note"),
        )
        return jsonify(line.to_dict()), 201
    except ReceiveDocumentNotFoundError:
        return jsonify({"error": "Receive document not found"}), 404
    except ReceiveDocumentStateError as e:
        return jsonify({"error": str(e)}), 409
    except ReceiveDocumentValidationError as e:
        return jsonify({"error": str(e)}), 400


@receives_bp.put("/<int:document_id>/lines/<int:line_id>")
@require_auth
@require_permission("RECEIVE_INVENTORY")
def update_line_route(document_id: int, line_id: int):
    """
    Update a line item on a receive document.

    Request body (all optional):
    {
        "quantity": 10,
        "unit_cost_cents": 1000,
        "note": "..."
    }

    Returns:
        Updated ReceiveDocumentLine object
    """
    data = request.get_json(silent=True) or {}

    try:
        line = receive_service.update_receive_line(
            line_id=line_id,
            quantity=data.get("quantity"),
            unit_cost_cents=data.get("unit_cost_cents"),
            note=data.get("note"),
        )
        return jsonify(line.to_dict())
    except ReceiveDocumentNotFoundError:
        return jsonify({"error": "Line not found"}), 404
    except ReceiveDocumentStateError as e:
        return jsonify({"error": str(e)}), 409
    except ReceiveDocumentValidationError as e:
        return jsonify({"error": str(e)}), 400


@receives_bp.delete("/<int:document_id>/lines/<int:line_id>")
@require_auth
@require_permission("RECEIVE_INVENTORY")
def remove_line_route(document_id: int, line_id: int):
    """
    Remove a line item from a receive document.
    """
    try:
        receive_service.remove_receive_line(line_id)
        return jsonify({"message": "Line removed"}), 200
    except ReceiveDocumentNotFoundError:
        return jsonify({"error": "Line not found"}), 404
    except ReceiveDocumentStateError as e:
        return jsonify({"error": str(e)}), 409


@receives_bp.post("/<int:document_id>/approve")
@require_auth
@require_permission("APPROVE_DOCUMENTS")
def approve_receive_route(document_id: int):
    """
    Approve a receive document.

    Moves document from DRAFT to APPROVED status.

    Returns:
        Approved ReceiveDocument object
    """
    user_id = g.current_user.id

    try:
        doc = receive_service.approve_receive_document(
            document_id=document_id,
            approved_by_user_id=user_id,
        )
        return jsonify(doc.to_dict())
    except ReceiveDocumentNotFoundError:
        return jsonify({"error": "Receive document not found"}), 404
    except ReceiveDocumentStateError as e:
        return jsonify({"error": str(e)}), 409
    except ReceiveDocumentValidationError as e:
        return jsonify({"error": str(e)}), 400


@receives_bp.post("/<int:document_id>/post")
@require_auth
@require_permission("POST_DOCUMENTS")
def post_receive_route(document_id: int):
    """
    Post a receive document to inventory.

    Creates InventoryTransaction records for each line.
    Moves document from APPROVED to POSTED status.

    Returns:
        Posted ReceiveDocument object
    """
    user_id = g.current_user.id

    try:
        doc = receive_service.post_receive_document(
            document_id=document_id,
            posted_by_user_id=user_id,
        )
        result = receive_service.get_receive_document_with_lines(document_id)
        return jsonify(result)
    except ReceiveDocumentNotFoundError:
        return jsonify({"error": "Receive document not found"}), 404
    except ReceiveDocumentStateError as e:
        return jsonify({"error": str(e)}), 409


@receives_bp.post("/<int:document_id>/cancel")
@require_auth
@require_any_permission("RECEIVE_INVENTORY", "APPROVE_DOCUMENTS")
def cancel_receive_route(document_id: int):
    """
    Cancel a receive document.

    Request body:
    {
        "reason": "Reason for cancellation"  // required
    }

    Returns:
        Cancelled ReceiveDocument object
    """
    user_id = g.current_user.id
    data = request.get_json(silent=True) or {}

    reason = data.get("reason")
    if not reason:
        return jsonify({"error": "reason is required"}), 400

    try:
        doc = receive_service.cancel_receive_document(
            document_id=document_id,
            cancelled_by_user_id=user_id,
            reason=reason,
        )
        return jsonify(doc.to_dict())
    except ReceiveDocumentNotFoundError:
        return jsonify({"error": "Receive document not found"}), 404
    except ReceiveDocumentStateError as e:
        return jsonify({"error": str(e)}), 409


@receives_bp.get("/types")
@require_auth
def get_receive_types_route():
    """
    Get list of valid receive types.

    Returns:
        {types: string[]}
    """
    return jsonify({"types": list(RECEIVE_TYPES)})
