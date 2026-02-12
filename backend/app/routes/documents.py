# Overview: Flask API routes for unified documents; parses input and returns JSON responses.

"""
Unified Documents Routes

Provides a consolidated index for operational documents.
"""

from flask import Blueprint, request, jsonify, g

from ..decorators import require_auth, require_permission
from ..services.document_service import list_documents, get_document, DOCUMENT_TYPES
from ..services.tenant_service import require_store_in_org, TenantAccessError, get_org_store_ids
from ..services import user_store_access_service
from app.time_utils import parse_iso_datetime


documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _allowed_report_store_ids() -> set[int]:
    # Developers keep org-wide report visibility when switched into an org.
    if getattr(g.current_user, "is_developer", False):
        return set(get_org_store_ids(g.org_id))
    return set(user_store_access_service.get_manager_store_ids(g.current_user.id, include_primary=True))


@documents_bp.get("")
@require_auth
@require_permission("VIEW_DOCUMENTS")
def list_documents_route():
    store_id = request.args.get("store_id", type=int)
    doc_type = request.args.get("type")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    user_id = request.args.get("user_id", type=int)
    register_id = request.args.get("register_id", type=int)
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    allowed_store_ids = _allowed_report_store_ids()
    if not allowed_store_ids:
        return jsonify({"items": [], "count": 0, "limit": limit, "offset": offset})

    if store_id:
        try:
            require_store_in_org(store_id, g.org_id)
        except TenantAccessError:
            return jsonify({"error": "Store not found"}), 404
        if store_id not in allowed_store_ids:
            return jsonify({"error": "Store access denied"}), 403
        store_ids = [store_id]
    else:
        store_ids = sorted(allowed_store_ids)

    if doc_type and doc_type not in DOCUMENT_TYPES:
        return jsonify({"error": f"Invalid type. Must be one of: {', '.join(DOCUMENT_TYPES.keys())}"}), 400

    from_dt = parse_iso_datetime(from_date) if from_date else None
    to_dt = parse_iso_datetime(to_date) if to_date else None
    if from_date and not from_dt:
        return jsonify({"error": "Invalid from_date"}), 400
    if to_date and not to_dt:
        return jsonify({"error": "Invalid to_date"}), 400

    rows, total = list_documents(
        store_id=None,
        store_ids=store_ids,
        doc_type=doc_type,
        from_date=from_dt,
        to_date=to_dt,
        user_id=user_id,
        register_id=register_id,
        limit=limit,
        offset=offset,
    )

    return jsonify({"items": rows, "count": total, "limit": limit, "offset": offset})


@documents_bp.get("/<doc_type>/<int:doc_id>")
@require_auth
@require_permission("VIEW_DOCUMENTS")
def get_document_route(doc_type: str, doc_id: int):
    doc_type = doc_type.upper()
    doc = get_document(doc_type, doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    # Enforce report visibility by manager-store scope.
    allowed_store_ids = _allowed_report_store_ids()
    store_id = doc.get("store_id")
    if store_id is None and doc_type == "TRANSFERS":
        store_id = doc.get("from_store_id")
    if store_id is None or store_id not in allowed_store_ids:
        return jsonify({"error": "Document not found"}), 404
    return jsonify({"document": doc})
