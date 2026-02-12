# Overview: Flask API routes for imports; parses input and returns JSON responses.

"""
Import Routes

Supports CSV, JSON, and Excel (.xlsx) uploads.
"""

import csv
import io
import json

from flask import Blueprint, request, jsonify, g

from ..decorators import require_auth, require_permission
from ..services import import_service
from ..services.import_service import ImportError


imports_bp = Blueprint("imports", __name__, url_prefix="/api/imports")


@imports_bp.post("/batches")
@require_auth
@require_permission("CREATE_IMPORTS")
def create_batch_route():
    data = request.get_json(silent=True) or {}
    import_type = data.get("import_type")
    source_file_name = data.get("source_file_name")
    source_file_format = data.get("source_file_format")

    if not import_type:
        return jsonify({"error": "import_type is required"}), 400

    try:
        batch = import_service.create_import_batch(
            org_id=g.org_id,
            import_type=import_type,
            created_by_user_id=g.current_user.id,
            source_file_name=source_file_name,
            source_file_format=source_file_format,
        )
        return jsonify({"batch": batch.to_dict()}), 201
    except ImportError as e:
        return jsonify({"error": str(e)}), 400


@imports_bp.post("/batches/<int:batch_id>/upload")
@require_auth
@require_permission("CREATE_IMPORTS")
def upload_batch_route(batch_id: int):
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    file = request.files["file"]
    filename = file.filename or ""
    ext = filename.split(".")[-1].lower()

    try:
        if ext == "csv":
            stream = io.StringIO(file.stream.read().decode("utf-8"))
            reader = csv.DictReader(stream)
            rows = [row for row in reader]
        elif ext == "json":
            rows = json.load(file.stream)
            if isinstance(rows, dict):
                rows = rows.get("rows", [])
        elif ext in {"xlsx", "xlsm", "xltx", "xltm"}:
            from openpyxl import load_workbook
            wb = load_workbook(file.stream, data_only=True)
            sheet = wb.active
            data = list(sheet.values)
            if not data:
                rows = []
            else:
                headers = [str(h) if h is not None else "" for h in data[0]]
                rows = [
                    {headers[i]: row[i] for i in range(len(headers))}
                    for row in data[1:]
                ]
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        result = import_service.stage_rows(batch_id=batch_id, org_id=g.org_id, rows=rows)
        return jsonify(result), 201
    except ImportError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        return jsonify({"error": "Failed to parse upload"}), 400


@imports_bp.post("/batches/<int:batch_id>/stage")
@require_auth
@require_permission("CREATE_IMPORTS")
def stage_rows_route(batch_id: int):
    data = request.get_json(silent=True) or {}
    rows = data.get("rows")
    if not isinstance(rows, list):
        return jsonify({"error": "rows must be a list"}), 400

    try:
        result = import_service.stage_rows(batch_id=batch_id, org_id=g.org_id, rows=rows)
        return jsonify(result), 201
    except ImportError as e:
        return jsonify({"error": str(e)}), 400


@imports_bp.get("/batches/<int:batch_id>/unmapped")
@require_auth
@require_permission("CREATE_IMPORTS")
def get_unmapped_route(batch_id: int):
    try:
        result = import_service.get_unmapped_entities(batch_id=batch_id, org_id=g.org_id)
        return jsonify(result)
    except ImportError as e:
        return jsonify({"error": str(e)}), 400


@imports_bp.post("/batches/<int:batch_id>/mappings")
@require_auth
@require_permission("CREATE_IMPORTS")
def set_mapping_route(batch_id: int):
    data = request.get_json(silent=True) or {}
    entity_type = data.get("entity_type")
    foreign_id = data.get("foreign_id")
    local_entity_id = data.get("local_entity_id")

    if not entity_type or not foreign_id or local_entity_id is None:
        return jsonify({"error": "entity_type, foreign_id, and local_entity_id are required"}), 400

    try:
        mapping = import_service.set_entity_mapping(
            batch_id=batch_id,
            org_id=g.org_id,
            entity_type=entity_type,
            foreign_id=str(foreign_id),
            local_entity_id=int(local_entity_id),
        )
        return jsonify({"mapping": mapping.to_dict()}), 201
    except ImportError as e:
        return jsonify({"error": str(e)}), 400


@imports_bp.post("/batches/<int:batch_id>/post")
@require_auth
@require_permission("APPROVE_IMPORTS")
def post_rows_route(batch_id: int):
    limit = request.args.get("limit", 200, type=int)
    try:
        result = import_service.post_mapped_rows(
            batch_id=batch_id,
            org_id=g.org_id,
            actor_user_id=g.current_user.id,
            limit=limit,
        )
        return jsonify(result)
    except ImportError as e:
        return jsonify({"error": str(e)}), 400


@imports_bp.get("/batches/<int:batch_id>/status")
@require_auth
@require_permission("CREATE_IMPORTS")
def batch_status_route(batch_id: int):
    try:
        result = import_service.get_batch_status(batch_id=batch_id, org_id=g.org_id)
        return jsonify({"batch": result})
    except ImportError as e:
        return jsonify({"error": str(e)}), 400


@imports_bp.get("/batches/<int:batch_id>/rows")
@require_auth
@require_permission("CREATE_IMPORTS")
def batch_rows_route(batch_id: int):
    status = request.args.get("status")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 100, type=int)
    try:
        result = import_service.list_batch_rows(
            batch_id=batch_id,
            org_id=g.org_id,
            status=status,
            page=page,
            per_page=per_page,
        )
        return jsonify(result), 200
    except ImportError as e:
        return jsonify({"error": str(e)}), 400
