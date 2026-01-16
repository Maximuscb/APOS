"""
Phase 7: Permission System Constants and Definitions

WHY: Centralized permission definitions ensure consistency across the application.
All permission codes and role mappings defined here.

DESIGN PRINCIPLES:
- Permissions are granular (one action per permission)
- Categories group related permissions for UI display
- Default role mappings follow principle of least privilege
- Admin has all permissions by default
"""

# =============================================================================
# PERMISSION CATEGORIES
# =============================================================================

class PermissionCategory:
    """Permission categories for organization."""
    INVENTORY = "INVENTORY"
    SALES = "SALES"
    USERS = "USERS"
    SYSTEM = "SYSTEM"
    DOCUMENTS = "DOCUMENTS"
    REGISTERS = "REGISTERS"



# =============================================================================
# PERMISSION DEFINITIONS
# =============================================================================

# Each permission is defined as: (code, name, description, category)
PERMISSION_DEFINITIONS = [
    # INVENTORY PERMISSIONS
    (
        "VIEW_INVENTORY",
        "View Inventory",
        "View inventory quantities and transactions",
        PermissionCategory.INVENTORY
    ),
    (
        "RECEIVE_INVENTORY",
        "Receive Inventory",
        "Create RECEIVE transactions (incoming stock)",
        PermissionCategory.INVENTORY
    ),
    (
        "ADJUST_INVENTORY",
        "Adjust Inventory",
        "Create ADJUST transactions (corrections, shrink, etc.)",
        PermissionCategory.INVENTORY
    ),
    (
        "APPROVE_ADJUSTMENTS",
        "Approve Adjustments",
        "Approve DRAFT inventory adjustments",
        PermissionCategory.INVENTORY
    ),
    (
        "VIEW_COGS",
        "View COGS",
        "View cost of goods sold and WAC calculations",
        PermissionCategory.INVENTORY
    ),

    # SALES PERMISSIONS
    (
        "CREATE_SALE",
        "Create Sale",
        "Create new sales documents (POS access)",
        PermissionCategory.SALES
    ),
    (
        "POST_SALE",
        "Post Sale",
        "Post sales to inventory (finalize transaction)",
        PermissionCategory.SALES
    ),
    (
        "VOID_SALE",
        "Void Sale",
        "Void posted sales (requires manager override)",
        PermissionCategory.SALES
    ),
    (
        "REFUND_PAYMENT",
        "Refund Payment",
        "Process payment refunds (negative payment transactions)",
        PermissionCategory.SALES
    ),
    (
        "PROCESS_RETURN",
        "Process Return",
        "Process product returns",
        PermissionCategory.SALES
    ),
    (
        "VIEW_SALES_REPORTS",
        "View Sales Reports",
        "Access sales reports and analytics",
        PermissionCategory.SALES
    ),
    (
        "CREATE_REGISTER",
        "Create Register",
        "Create new POS registers/devices",
        PermissionCategory.REGISTERS
    ),
    (
        "MANAGE_REGISTER",
        "Manage Registers",
        "Create/edit/deactivate registers and register settings",
        PermissionCategory.REGISTERS
    ),

    # DOCUMENT LIFECYCLE PERMISSIONS
    (
        "APPROVE_DOCUMENTS",
        "Approve Documents",
        "Approve DRAFT documents (DRAFT -> APPROVED)",
        PermissionCategory.DOCUMENTS
    ),
    (
        "POST_DOCUMENTS",
        "Post Documents",
        "Post documents to ledger (APPROVED -> POSTED)",
        PermissionCategory.DOCUMENTS
    ),
    (
        "VIEW_DOCUMENTS",
        "View Documents",
        "View documents and their details",
        PermissionCategory.DOCUMENTS
    ),
    (
        "CREATE_TRANSFERS",
        "Create Transfers",
        "Create inter-store transfer documents",
        PermissionCategory.DOCUMENTS
    ),
    (
        "CREATE_COUNTS",
        "Create Counts",
        "Create physical inventory count documents",
        PermissionCategory.DOCUMENTS
    ),

    # USER MANAGEMENT PERMISSIONS
    (
        "VIEW_USERS",
        "View Users",
        "View user accounts and roles",
        PermissionCategory.USERS
    ),
    (
        "CREATE_USER",
        "Create User",
        "Create new user accounts",
        PermissionCategory.USERS
    ),
    (
        "EDIT_USER",
        "Edit User",
        "Edit user account details",
        PermissionCategory.USERS
    ),
    (
        "ASSIGN_ROLES",
        "Assign Roles",
        "Assign roles to users",
        PermissionCategory.USERS
    ),
    (
        "DEACTIVATE_USER",
        "Deactivate User",
        "Deactivate user accounts",
        PermissionCategory.USERS
    ),

    # SYSTEM PERMISSIONS
    (
        "MANAGE_PRODUCTS",
        "Manage Products",
        "Create, edit, and deactivate products",
        PermissionCategory.SYSTEM
    ),
    (
        "MANAGE_IDENTIFIERS",
        "Manage Identifiers",
        "Add/edit product identifiers (barcodes, SKUs)",
        PermissionCategory.SYSTEM
    ),
    (
        "VIEW_AUDIT_LOG",
        "View Audit Log",
        "Access security and audit logs",
        PermissionCategory.SYSTEM
    ),
    (
        "VIEW_STORES",
        "View Stores",
        "View store details and hierarchy",
        PermissionCategory.SYSTEM
    ),
    (
        "MANAGE_STORES",
        "Manage Stores",
        "Create and update stores and store configuration",
        PermissionCategory.SYSTEM
    ),
    (
        "MANAGE_PERMISSIONS",
        "Manage Permissions",
        "Grant/revoke permissions (admin only)",
        PermissionCategory.SYSTEM
    ),
    (
        "SYSTEM_ADMIN",
        "System Administration",
        "Full system access (admin only)",
        PermissionCategory.SYSTEM
    ),
]


# =============================================================================
# DEFAULT ROLE PERMISSION MAPPINGS
# =============================================================================

# WHY these mappings:
# - ADMIN: Full access to everything (trust model)
# - DEVELOPER: Full access including role assignment (for development/testing)
# - MANAGER: Can approve, manage inventory, view reports, manage users
# - CASHIER: POS only (create/post sales, view inventory for selling)

DEFAULT_ROLE_PERMISSIONS = {
    "admin": [
        # Admin gets ALL permissions
        "CREATE_REGISTER",
        "MANAGE_REGISTER",
        "VIEW_INVENTORY",
        "RECEIVE_INVENTORY",
        "ADJUST_INVENTORY",
        "APPROVE_ADJUSTMENTS",
        "VIEW_COGS",
        "CREATE_SALE",
        "POST_SALE",
        "VOID_SALE",
        "REFUND_PAYMENT",
        "PROCESS_RETURN",
        "VIEW_SALES_REPORTS",
        "APPROVE_DOCUMENTS",
        "POST_DOCUMENTS",
        "VIEW_DOCUMENTS",
        "CREATE_TRANSFERS",
        "CREATE_COUNTS",
        "VIEW_USERS",
        "CREATE_USER",
        "EDIT_USER",
        "ASSIGN_ROLES",
        "DEACTIVATE_USER",
        "MANAGE_PRODUCTS",
        "MANAGE_IDENTIFIERS",
        "VIEW_AUDIT_LOG",
        "VIEW_STORES",
        "MANAGE_STORES",
        "MANAGE_PERMISSIONS",
        "SYSTEM_ADMIN",
    ],

    "developer": [
        # Developer: Full system access including role assignment
        # Used for development and testing environments
        # Has all permissions to facilitate testing and debugging
        "CREATE_REGISTER",
        "MANAGE_REGISTER",
        "VIEW_INVENTORY",
        "RECEIVE_INVENTORY",
        "ADJUST_INVENTORY",
        "APPROVE_ADJUSTMENTS",
        "VIEW_COGS",
        "CREATE_SALE",
        "POST_SALE",
        "VOID_SALE",
        "REFUND_PAYMENT",
        "PROCESS_RETURN",
        "VIEW_SALES_REPORTS",
        "APPROVE_DOCUMENTS",
        "POST_DOCUMENTS",
        "VIEW_DOCUMENTS",
        "CREATE_TRANSFERS",
        "CREATE_COUNTS",
        "VIEW_USERS",
        "CREATE_USER",
        "EDIT_USER",
        "ASSIGN_ROLES",
        "DEACTIVATE_USER",
        "MANAGE_PRODUCTS",
        "MANAGE_IDENTIFIERS",
        "VIEW_AUDIT_LOG",
        "VIEW_STORES",
        "MANAGE_STORES",
        "MANAGE_PERMISSIONS",
        "SYSTEM_ADMIN",
    ],

    "manager": [
        # Manager: Approvals, inventory management, user management, reports
        "CREATE_REGISTER",
        "MANAGE_REGISTER",
        "VIEW_INVENTORY",
        "RECEIVE_INVENTORY",
        "ADJUST_INVENTORY",
        "APPROVE_ADJUSTMENTS",
        "VIEW_COGS",
        "CREATE_SALE",
        "POST_SALE",
        "VOID_SALE",  # Manager can void sales
        "REFUND_PAYMENT",
        "PROCESS_RETURN",
        "VIEW_SALES_REPORTS",
        "APPROVE_DOCUMENTS",
        "POST_DOCUMENTS",
        "VIEW_DOCUMENTS",
        "CREATE_TRANSFERS",
        "CREATE_COUNTS",
        "VIEW_USERS",
        "CREATE_USER",  # Manager can create cashier accounts
        "EDIT_USER",
        "MANAGE_PRODUCTS",
        "MANAGE_IDENTIFIERS",
        "VIEW_AUDIT_LOG",
        "VIEW_STORES",
        "MANAGE_STORES",
    ],

    "cashier": [
        # Cashier: POS operations only
        "VIEW_INVENTORY",  # Need to see what's in stock
        "CREATE_SALE",     # Primary job: ring up sales
        "POST_SALE",       # Finalize sales
        "PROCESS_RETURN",  # Handle returns
    ],
}


# =============================================================================
# PERMISSION HELPERS
# =============================================================================

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
