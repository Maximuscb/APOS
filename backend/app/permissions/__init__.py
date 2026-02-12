# Overview: Permission system package.
# Re-exports all public APIs for backwards-compatible imports.

from .categories import PermissionCategory
from .definitions import (
    PERMISSION_DEFINITIONS,
    INVENTORY_PERMISSIONS,
    SALES_PERMISSIONS,
    REGISTER_PERMISSIONS,
    DOCUMENT_PERMISSIONS,
    USER_PERMISSIONS,
    SYSTEM_PERMISSIONS,
    TIMEKEEPING_PERMISSIONS,
    COMMUNICATION_PERMISSIONS,
    PROMOTION_PERMISSIONS,
    ORGANIZATION_PERMISSIONS,
    DEVICE_PERMISSIONS,
)
from .roles import DEFAULT_ROLE_PERMISSIONS
from .helpers import (
    get_all_permission_codes,
    get_permissions_by_category,
    get_permission_definition,
    validate_permission_code,
)

__all__ = [
    "PermissionCategory",
    "PERMISSION_DEFINITIONS",
    "INVENTORY_PERMISSIONS",
    "SALES_PERMISSIONS",
    "REGISTER_PERMISSIONS",
    "DOCUMENT_PERMISSIONS",
    "USER_PERMISSIONS",
    "SYSTEM_PERMISSIONS",
    "TIMEKEEPING_PERMISSIONS",
    "COMMUNICATION_PERMISSIONS",
    "PROMOTION_PERMISSIONS",
    "ORGANIZATION_PERMISSIONS",
    "DEVICE_PERMISSIONS",
    "DEFAULT_ROLE_PERMISSIONS",
    "get_all_permission_codes",
    "get_permissions_by_category",
    "get_permission_definition",
    "validate_permission_code",
]
