# Overview: All permission definitions organized by category.
# Each permission is defined as: (code, name, description, category)

from .categories import PermissionCategory


# -- INVENTORY --

INVENTORY_PERMISSIONS = [
    (
        "VIEW_INVENTORY",
        "View Inventory",
        "View inventory quantities and transactions",
        PermissionCategory.INVENTORY,
    ),
    (
        "RECEIVE_INVENTORY",
        "Receive Inventory",
        "Create RECEIVE transactions (incoming stock)",
        PermissionCategory.INVENTORY,
    ),
    (
        "ADJUST_INVENTORY",
        "Adjust Inventory",
        "Create ADJUST transactions (corrections, shrink, etc.)",
        PermissionCategory.INVENTORY,
    ),
    (
        "APPROVE_ADJUSTMENTS",
        "Approve Adjustments",
        "Approve DRAFT inventory adjustments",
        PermissionCategory.INVENTORY,
    ),
    (
        "VIEW_COGS",
        "View COGS",
        "View cost of goods sold and WAC calculations",
        PermissionCategory.INVENTORY,
    ),
    (
        "VIEW_VENDORS",
        "View Vendors",
        "View vendor list",
        PermissionCategory.INVENTORY,
    ),
    (
        "MANAGE_VENDORS",
        "Manage Vendors",
        "Create and edit vendors",
        PermissionCategory.INVENTORY,
    ),
]


# -- SALES --

SALES_PERMISSIONS = [
    (
        "CREATE_SALE",
        "Create Sale",
        "Create new sales documents (POS access)",
        PermissionCategory.SALES,
    ),
    (
        "POST_SALE",
        "Post Sale",
        "Post sales to inventory (finalize transaction)",
        PermissionCategory.SALES,
    ),
    (
        "VOID_SALE",
        "Void Sale",
        "Void posted sales (requires manager override)",
        PermissionCategory.SALES,
    ),
    (
        "REFUND_PAYMENT",
        "Refund Payment",
        "Process payment refunds (negative payment transactions)",
        PermissionCategory.SALES,
    ),
    (
        "PROCESS_RETURN",
        "Process Return",
        "Process product returns",
        PermissionCategory.SALES,
    ),
    (
        "VIEW_SALES_REPORTS",
        "View Sales Reports",
        "Access sales reports and analytics",
        PermissionCategory.SALES,
    ),
]


# -- REGISTERS --

REGISTER_PERMISSIONS = [
    (
        "CREATE_REGISTER",
        "Create Register",
        "Create new POS registers/devices",
        PermissionCategory.REGISTERS,
    ),
    (
        "MANAGE_REGISTER",
        "Manage Registers",
        "Create/edit/deactivate registers and register settings",
        PermissionCategory.REGISTERS,
    ),
]


# -- DOCUMENTS --

DOCUMENT_PERMISSIONS = [
    (
        "APPROVE_DOCUMENTS",
        "Approve Documents",
        "Approve DRAFT documents (DRAFT -> APPROVED)",
        PermissionCategory.DOCUMENTS,
    ),
    (
        "POST_DOCUMENTS",
        "Post Documents",
        "Post documents to ledger (APPROVED -> POSTED)",
        PermissionCategory.DOCUMENTS,
    ),
    (
        "VIEW_DOCUMENTS",
        "View Documents",
        "View documents and their details",
        PermissionCategory.DOCUMENTS,
    ),
    (
        "CREATE_TRANSFERS",
        "Create Transfers",
        "Create inter-store transfer documents",
        PermissionCategory.DOCUMENTS,
    ),
    (
        "CREATE_COUNTS",
        "Create Counts",
        "Create physical inventory count documents",
        PermissionCategory.DOCUMENTS,
    ),
]


# -- USERS --

USER_PERMISSIONS = [
    (
        "VIEW_USERS",
        "View Users",
        "View user accounts and roles",
        PermissionCategory.USERS,
    ),
    (
        "CREATE_USER",
        "Create User",
        "Create new user accounts",
        PermissionCategory.USERS,
    ),
    (
        "EDIT_USER",
        "Edit User",
        "Edit user account details",
        PermissionCategory.USERS,
    ),
    (
        "ASSIGN_ROLES",
        "Assign Roles",
        "Assign roles to users",
        PermissionCategory.USERS,
    ),
    (
        "DEACTIVATE_USER",
        "Deactivate User",
        "Deactivate user accounts",
        PermissionCategory.USERS,
    ),
]


# -- SYSTEM --

SYSTEM_PERMISSIONS = [
    (
        "MANAGE_PRODUCTS",
        "Manage Products",
        "Create, edit, and deactivate products",
        PermissionCategory.SYSTEM,
    ),
    (
        "MANAGE_IDENTIFIERS",
        "Manage Identifiers",
        "Add/edit product identifiers (barcodes, SKUs)",
        PermissionCategory.SYSTEM,
    ),
    (
        "VIEW_AUDIT_LOG",
        "View Audit Log",
        "Access security and audit logs",
        PermissionCategory.SYSTEM,
    ),
    (
        "VIEW_STORES",
        "View Stores",
        "View store details and hierarchy",
        PermissionCategory.SYSTEM,
    ),
    (
        "MANAGE_STORES",
        "Manage Stores",
        "Create and update stores and store configuration",
        PermissionCategory.SYSTEM,
    ),
    (
        "SWITCH_STORE",
        "Switch Store",
        "Switch between stores within the organization",
        PermissionCategory.SYSTEM,
    ),
    (
        "MANAGE_PERMISSIONS",
        "Manage Permissions",
        "Grant/revoke permissions (admin only)",
        PermissionCategory.SYSTEM,
    ),
    (
        "SYSTEM_ADMIN",
        "System Administration",
        "Full system access (admin only)",
        PermissionCategory.SYSTEM,
    ),
    (
        "CREATE_IMPORTS",
        "Create Imports",
        "Create and manage import batches",
        PermissionCategory.SYSTEM,
    ),
    (
        "APPROVE_IMPORTS",
        "Approve Imports",
        "Approve and post imports",
        PermissionCategory.SYSTEM,
    ),
    (
        "VIEW_ANALYTICS",
        "View Analytics",
        "View analytics and reports",
        PermissionCategory.SYSTEM,
    ),
    (
        "VIEW_CROSS_STORE_ANALYTICS",
        "View Cross-Store Analytics",
        "View org-wide analytics",
        PermissionCategory.SYSTEM,
    ),
    (
        "DEVELOPER_ACCESS",
        "Developer Access",
        "Cross-organization developer access",
        PermissionCategory.SYSTEM,
    ),
]


# -- TIMEKEEPING --

TIMEKEEPING_PERMISSIONS = [
    (
        "CLOCK_IN_OUT",
        "Clock In/Out",
        "Clock in and out for shifts",
        PermissionCategory.TIMEKEEPING,
    ),
    (
        "VIEW_TIMEKEEPING",
        "View Timekeeping",
        "View time entries and reports",
        PermissionCategory.TIMEKEEPING,
    ),
    (
        "APPROVE_TIME_CORRECTIONS",
        "Approve Time Corrections",
        "Approve time clock corrections",
        PermissionCategory.TIMEKEEPING,
    ),
    (
        "MANAGE_TIMEKEEPING",
        "Manage Timekeeping",
        "Full timekeeping administration",
        PermissionCategory.TIMEKEEPING,
    ),
]


# -- COMMUNICATIONS --

COMMUNICATION_PERMISSIONS = [
    (
        "VIEW_COMMUNICATIONS",
        "View Communications",
        "View announcements, reminders, and tasks",
        PermissionCategory.COMMUNICATIONS,
    ),
    (
        "MANAGE_COMMUNICATIONS",
        "Manage Communications",
        "Create and edit announcements, reminders, and tasks",
        PermissionCategory.COMMUNICATIONS,
    ),
]


# -- PROMOTIONS --

PROMOTION_PERMISSIONS = [
    (
        "VIEW_PROMOTIONS",
        "View Promotions",
        "View promotions and discounts",
        PermissionCategory.PROMOTIONS,
    ),
    (
        "MANAGE_PROMOTIONS",
        "Manage Promotions",
        "Create, edit, and deactivate promotions",
        PermissionCategory.PROMOTIONS,
    ),
]


# -- ORGANIZATION --

ORGANIZATION_PERMISSIONS = [
    (
        "VIEW_ORGANIZATION",
        "View Organization",
        "View organization details and structure",
        PermissionCategory.ORGANIZATION,
    ),
    (
        "MANAGE_ORGANIZATION",
        "Manage Organization",
        "Organization-level administration (stores, structure)",
        PermissionCategory.ORGANIZATION,
    ),
]


# -- DEVICES --

DEVICE_PERMISSIONS = [
    (
        "VIEW_DEVICE_SETTINGS",
        "View Device Settings",
        "View device configurations",
        PermissionCategory.DEVICES,
    ),
    (
        "MANAGE_DEVICE_SETTINGS",
        "Manage Device Settings",
        "Configure device-level settings",
        PermissionCategory.DEVICES,
    ),
]


# Combined list of all permissions (preserves original ordering)
PERMISSION_DEFINITIONS = (
    INVENTORY_PERMISSIONS
    + SALES_PERMISSIONS
    + REGISTER_PERMISSIONS
    + DOCUMENT_PERMISSIONS
    + USER_PERMISSIONS
    + SYSTEM_PERMISSIONS
    + TIMEKEEPING_PERMISSIONS
    + COMMUNICATION_PERMISSIONS
    + PROMOTION_PERMISSIONS
    + ORGANIZATION_PERMISSIONS
    + DEVICE_PERMISSIONS
)
