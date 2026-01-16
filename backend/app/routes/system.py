# backend/app/routes/system.py
"""
System health and version endpoints.

Provides comprehensive health checks for all system dependencies and
version information for deployment debugging.
"""

import os
import time
from flask import Blueprint, current_app
from ..extensions import db
from ..models import Store, User, Role, Permission, SessionToken
from app.time_utils import utcnow

system_bp = Blueprint("system", __name__)


def check_database_health() -> dict:
    """
    Check database connectivity and basic operations.

    Returns dict with status and details.
    """
    start_time = time.time()
    try:
        # Test basic query - count stores
        store_count = db.session.query(Store).count()

        # Test user table
        user_count = db.session.query(User).count()

        # Test role table
        role_count = db.session.query(Role).count()

        # Test permission table
        permission_count = db.session.query(Permission).count()

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "status": "healthy",
            "latency_ms": round(elapsed_ms, 2),
            "details": {
                "stores": store_count,
                "users": user_count,
                "roles": role_count,
                "permissions": permission_count,
            }
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        current_app.logger.exception("Database health check failed")
        return {
            "status": "unhealthy",
            "latency_ms": round(elapsed_ms, 2),
            "error": "Database error"
        }


def check_session_service_health() -> dict:
    """
    Check session service health by verifying session table accessibility.
    """
    start_time = time.time()
    try:
        # Count active sessions
        active_sessions = db.session.query(SessionToken).filter_by(
            is_revoked=False
        ).count()

        # Count expired sessions (could be cleaned up)
        now = utcnow()
        expired_sessions = db.session.query(SessionToken).filter(
            SessionToken.expires_at < now,
            SessionToken.is_revoked == False
        ).count()

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "status": "healthy",
            "latency_ms": round(elapsed_ms, 2),
            "details": {
                "active_sessions": active_sessions,
                "expired_pending_cleanup": expired_sessions,
            }
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        current_app.logger.exception("Session service health check failed")
        return {
            "status": "unhealthy",
            "latency_ms": round(elapsed_ms, 2),
            "error": "Session service error"
        }


def check_auth_service_health() -> dict:
    """
    Check authentication service health by verifying roles and permissions exist.
    """
    start_time = time.time()
    try:
        # Verify essential roles exist
        essential_roles = ["admin", "manager", "cashier"]
        missing_roles = []

        for role_name in essential_roles:
            role = db.session.query(Role).filter_by(name=role_name).first()
            if not role:
                missing_roles.append(role_name)

        # Verify permissions are initialized
        permission_count = db.session.query(Permission).count()

        elapsed_ms = (time.time() - start_time) * 1000

        if missing_roles:
            return {
                "status": "degraded",
                "latency_ms": round(elapsed_ms, 2),
                "warning": f"Missing roles: {', '.join(missing_roles)}",
                "details": {
                    "permissions_initialized": permission_count > 0,
                    "permission_count": permission_count,
                }
            }

        return {
            "status": "healthy",
            "latency_ms": round(elapsed_ms, 2),
            "details": {
                "roles_configured": True,
                "permissions_initialized": permission_count > 0,
                "permission_count": permission_count,
            }
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        current_app.logger.exception("Auth service health check failed")
        return {
            "status": "unhealthy",
            "latency_ms": round(elapsed_ms, 2),
            "error": "Auth service error"
        }


@system_bp.get("/health")
def health():
    """
    Comprehensive health check endpoint.

    Checks all critical system dependencies:
    - Database connectivity and basic queries
    - Session service health
    - Authentication service health (roles/permissions)

    Returns:
    - 200: All systems healthy
    - 503: One or more systems unhealthy

    Response includes detailed status for each component.
    """
    start_time = time.time()

    # Check all dependencies
    database_health = check_database_health()
    session_health = check_session_service_health()
    auth_health = check_auth_service_health()

    # Determine overall status
    all_checks = [database_health, session_health, auth_health]
    unhealthy_count = sum(1 for check in all_checks if check["status"] == "unhealthy")
    degraded_count = sum(1 for check in all_checks if check["status"] == "degraded")

    if unhealthy_count > 0:
        overall_status = "unhealthy"
        http_status = 503
    elif degraded_count > 0:
        overall_status = "degraded"
        http_status = 200  # Degraded is still operational
    else:
        overall_status = "healthy"
        http_status = 200

    total_elapsed_ms = (time.time() - start_time) * 1000

    response = {
        "status": overall_status,
        "timestamp": utcnow().isoformat() + "Z",
        "total_latency_ms": round(total_elapsed_ms, 2),
        "checks": {
            "database": database_health,
            "session_service": session_health,
            "auth_service": auth_health,
        }
    }

    return response, http_status


@system_bp.get("/version")
def version():
    """
    Version endpoint for deployment debugging.

    Returns non-sensitive information about the deployment:
    - API version
    - Environment (development/production)
    - Python version
    - Server timestamp

    Does NOT expose:
    - Secret keys
    - Database credentials
    - Internal paths
    """
    import sys

    # Determine environment from Flask config
    env = "production" if not current_app.debug else "development"

    return {
        "api_version": "1.3.0",
        "environment": env,
        "python_version": sys.version.split()[0],
        "server_time": utcnow().isoformat() + "Z",
    }
