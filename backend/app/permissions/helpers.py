# Overview: Utility functions for permission lookups and validation.

from .definitions import PERMISSION_DEFINITIONS


def get_all_permission_codes():
    """Get list of all permission codes."""
    return [perm[0] for perm in PERMISSION_DEFINITIONS]


def get_permissions_by_category(category):
    """Get all permissions in a category."""
    return [perm for perm in PERMISSION_DEFINITIONS if perm[3] == category]


def get_permission_definition(code):
    """Get full definition for a permission code."""
    for perm in PERMISSION_DEFINITIONS:
        if perm[0] == code:
            return {
                "code": perm[0],
                "name": perm[1],
                "description": perm[2],
                "category": perm[3],
            }
    return None


def validate_permission_code(code):
    """Check if a permission code is valid."""
    return code in get_all_permission_codes()
