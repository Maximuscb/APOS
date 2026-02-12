from __future__ import annotations

import os

from flask import Blueprint, jsonify, request, g
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..decorators import require_auth, require_developer
from ..models import Organization, SessionToken, Store
from ..services import session_service
from ..services.ledger_service import ensure_org_master_ledger

developer_bp = Blueprint("developer", __name__, url_prefix="/api/developer")


@developer_bp.before_request
def _check_developer_tools_enabled():
    """Kill switch: set APOS_DEVELOPER_TOOLS=false to disable all developer endpoints."""
    if os.environ.get("APOS_DEVELOPER_TOOLS", "true").lower() == "false":
        return jsonify({"error": "Developer tools are disabled in this environment"}), 403


@developer_bp.route("/organizations", methods=["GET"])
@require_auth
@require_developer
def list_organizations():
    """List all organizations (developer only)."""
    orgs = db.session.query(Organization).order_by(Organization.name).all()
    return jsonify([o.to_dict() for o in orgs])


@developer_bp.route("/organizations", methods=["POST"])
@require_auth
@require_developer
def create_organization():
    """Create an organization and optional initial store (developer only)."""
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip() or None
    initial_store_name = (data.get("initial_store_name") or "").strip()

    if not name:
        return jsonify({"error": "name is required"}), 400

    org = Organization(name=name, code=code, is_active=True)
    db.session.add(org)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Organization code already exists"}), 400

    created_store = None
    if initial_store_name:
        created_store = Store(org_id=org.id, name=initial_store_name)
        db.session.add(created_store)

    ensure_org_master_ledger(org.id)

    db.session.commit()

    return jsonify({
        "organization": org.to_dict(),
        "store": created_store.to_dict() if created_store else None,
    }), 201


@developer_bp.route("/switch-org", methods=["POST"])
@require_auth
@require_developer
def switch_org():
    """
    Switch developer session to a different organization.

    Creates a new session token with the target org context.
    The old session remains valid (caller should discard it).
    """
    data = request.get_json() or {}
    org_id = data.get("org_id")

    if not org_id:
        return jsonify({"error": "org_id is required"}), 400

    org = db.session.query(Organization).filter_by(id=org_id, is_active=True).first()
    if not org:
        return jsonify({"error": "Organization not found or inactive"}), 404

    # Revoke the current session
    current_session = g.session_context.session
    current_session.is_revoked = True
    current_session.revoked_reason = f"Developer switched to org {org_id}"
    db.session.commit()

    # Create a new session with the target org context
    user = g.current_user
    plaintext_token = session_service.generate_token()
    token_hash = session_service.hash_token(plaintext_token)

    now = session_service.utcnow()
    new_session = SessionToken(
        user_id=user.id,
        org_id=org_id,
        store_id=None,
        token_hash=token_hash,
        created_at=now,
        last_used_at=now,
        expires_at=now + session_service.SESSION_ABSOLUTE_TIMEOUT,
        user_agent=request.headers.get("User-Agent"),
        ip_address=request.remote_addr,
        is_revoked=False,
    )
    db.session.add(new_session)
    db.session.commit()

    return jsonify({
        "token": plaintext_token,
        "org_id": org_id,
        "org_name": org.name,
        "store_id": None,
        "store_name": None,
    })


@developer_bp.route("/status", methods=["GET"])
@require_auth
@require_developer
def developer_status():
    """Get current developer session context."""
    user = g.current_user
    org = None
    if g.org_id:
        org = db.session.query(Organization).filter_by(id=g.org_id).first()

    return jsonify({
        "is_developer": True,
        "user_id": user.id,
        "username": user.username,
        "org_id": g.org_id,
        "org_name": org.name if org else None,
        "store_id": g.store_id,
    })
