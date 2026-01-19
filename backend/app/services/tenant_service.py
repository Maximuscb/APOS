"""
Multi-Tenant Service: Tenant Validation and Scoping Helpers

WHY: Centralize tenant validation logic for reuse across services and routes.
Every request must be scoped to a tenant (organization), and cross-tenant
access must be explicitly denied.

SECURITY INVARIANTS:
1. Every authenticated request has g.org_id set
2. Store IDs from client input must be validated against g.org_id
3. Queries touching store-owned data must filter by validated stores
4. Cross-tenant access attempts are logged as security events

USAGE:
    from app.services.tenant_service import require_store_in_org, get_org_stores

    # Validate store belongs to tenant
    require_store_in_org(store_id, g.org_id)

    # Get all stores for tenant
    stores = get_org_stores(g.org_id)
"""

from flask import g, request
from ..extensions import db
from ..models import Store, Organization
from .permission_service import log_security_event


class TenantAccessError(Exception):
    """Raised when cross-tenant access is attempted."""
    pass


def get_current_org_id() -> int:
    """
    Get current tenant's org_id from Flask g context.

    SECURITY: Raises TenantAccessError if org_id not set.
    This should never happen after @require_auth, but is a safety check.
    """
    if not hasattr(g, 'org_id') or g.org_id is None:
        raise TenantAccessError("Tenant context not established")
    return g.org_id


def get_current_store_id() -> int | None:
    """
    Get current user's store_id from Flask g context.

    Returns None for org-level users who aren't assigned to a specific store.
    """
    return getattr(g, 'store_id', None)


def require_store_in_org(store_id: int, org_id: int) -> Store:
    """
    Validate that a store belongs to the specified organization.

    SECURITY: Core tenant isolation check. Call this before any operation
    that uses a store_id from client input.

    Args:
        store_id: The store ID to validate (typically from request)
        org_id: The organization ID to check against (typically from g.org_id)

    Returns:
        The Store object if valid

    Raises:
        TenantAccessError if store doesn't exist or belongs to different org

    Usage:
        store = require_store_in_org(request_store_id, g.org_id)
    """
    store = db.session.query(Store).filter_by(id=store_id).first()

    if not store:
        # Log security event - could be probing
        _log_cross_tenant_attempt(
            f"Store {store_id} not found",
            org_id=org_id
        )
        raise TenantAccessError(f"Store not found")

    if store.org_id != org_id:
        # CRITICAL: Cross-tenant access attempt
        _log_cross_tenant_attempt(
            f"Store {store_id} belongs to org {store.org_id}, not {org_id}",
            org_id=org_id,
            attempted_store_id=store_id
        )
        raise TenantAccessError(f"Store not found")  # Don't reveal it exists in another org

    return store


def require_stores_in_org(store_ids: list[int], org_id: int) -> list[Store]:
    """
    Validate multiple stores belong to the specified organization.

    SECURITY: Batch validation for operations involving multiple stores
    (e.g., transfers between stores).

    Args:
        store_ids: List of store IDs to validate
        org_id: The organization ID to check against

    Returns:
        List of Store objects if all valid

    Raises:
        TenantAccessError if any store doesn't exist or belongs to different org
    """
    if not store_ids:
        return []

    stores = db.session.query(Store).filter(Store.id.in_(store_ids)).all()

    # Check all requested stores were found
    found_ids = {s.id for s in stores}
    missing_ids = set(store_ids) - found_ids

    if missing_ids:
        _log_cross_tenant_attempt(
            f"Stores not found: {missing_ids}",
            org_id=org_id
        )
        raise TenantAccessError("One or more stores not found")

    # Check all stores belong to the org
    for store in stores:
        if store.org_id != org_id:
            _log_cross_tenant_attempt(
                f"Store {store.id} belongs to org {store.org_id}, not {org_id}",
                org_id=org_id,
                attempted_store_id=store.id
            )
            raise TenantAccessError("One or more stores not found")

    return stores


def get_org_stores(org_id: int, active_only: bool = True) -> list[Store]:
    """
    Get all stores for an organization.

    Args:
        org_id: The organization ID
        active_only: If True, only return active stores

    Returns:
        List of Store objects belonging to the organization
    """
    query = db.session.query(Store).filter_by(org_id=org_id)

    # Note: Store doesn't have is_active yet, but Organization does
    # If we add is_active to Store later, add: .filter_by(is_active=True)

    return query.order_by(Store.name).all()


def get_org_store_ids(org_id: int) -> set[int]:
    """
    Get set of store IDs for an organization.

    Useful for quick membership checks without loading full objects.

    Args:
        org_id: The organization ID

    Returns:
        Set of store IDs belonging to the organization
    """
    stores = db.session.query(Store.id).filter_by(org_id=org_id).all()
    return {s.id for s in stores}


def validate_org_active(org_id: int) -> Organization:
    """
    Validate that an organization exists and is active.

    Args:
        org_id: The organization ID to validate

    Returns:
        The Organization object if valid and active

    Raises:
        TenantAccessError if org doesn't exist or is inactive
    """
    org = db.session.query(Organization).filter_by(id=org_id).first()

    if not org:
        raise TenantAccessError("Organization not found")

    if not org.is_active:
        raise TenantAccessError("Organization is not active")

    return org


def scoped_query(model, org_id: int = None):
    """
    Create a base query scoped to the current tenant via store_id.

    For models that have a store_id column, this filters to only stores
    belonging to the specified organization.

    Args:
        model: SQLAlchemy model class (must have store_id column)
        org_id: Organization ID (defaults to g.org_id)

    Returns:
        SQLAlchemy query filtered to tenant's stores

    Usage:
        products = scoped_query(Product).filter_by(is_active=True).all()
    """
    if org_id is None:
        org_id = get_current_org_id()

    # Get store IDs for this org
    store_ids = get_org_store_ids(org_id)

    return db.session.query(model).filter(model.store_id.in_(store_ids))


def _log_cross_tenant_attempt(
    reason: str,
    org_id: int | None = None,
    attempted_store_id: int | None = None
) -> None:
    """
    Log a cross-tenant access attempt as a security event.

    SECURITY: Critical audit trail for detecting unauthorized access attempts.
    These events should be monitored and alerted on.
    """
    user_id = getattr(g, 'current_user', None)
    if user_id and hasattr(user_id, 'id'):
        user_id = user_id.id

    log_security_event(
        user_id=user_id,
        event_type="CROSS_TENANT_ACCESS_DENIED",
        success=False,
        resource=request.path if request else None,
        action=request.method if request else None,
        reason=reason,
        ip_address=request.remote_addr if request else None,
        user_agent=request.headers.get("User-Agent") if request else None,
        org_id=org_id,
        store_id=attempted_store_id
    )
