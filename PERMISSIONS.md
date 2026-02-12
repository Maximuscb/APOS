# APOS 1.3 — Permissions Reference

## Permission Flow

```
User
  └─ UserRole (many)
       └─ Role (org-scoped)
            └─ RolePermission (many)
                 └─ Permission (global code)
  └─ UserPermissionOverride (per-user GRANT/DENY)
```

Effective permissions = union of all role permissions, plus GRANT overrides, minus DENY overrides.
`DEVELOPER_ACCESS` is protected — it cannot be granted or denied via overrides.

---

## Permission Registry

### INVENTORY

| Code | Name | Description |
|------|------|-------------|
| `VIEW_INVENTORY` | View Inventory | View inventory quantities and transactions |
| `RECEIVE_INVENTORY` | Receive Inventory | Create RECEIVE transactions (incoming stock) |
| `ADJUST_INVENTORY` | Adjust Inventory | Create ADJUST transactions (corrections, shrink) |
| `APPROVE_ADJUSTMENTS` | Approve Adjustments | Approve DRAFT inventory adjustments |
| `VIEW_COGS` | View COGS | View cost of goods sold and WAC calculations |
| `VIEW_VENDORS` | View Vendors | View vendor list |
| `MANAGE_VENDORS` | Manage Vendors | Create and edit vendors |

### SALES

| Code | Name | Description |
|------|------|-------------|
| `CREATE_SALE` | Create Sale | Create new sales documents (POS access) |
| `POST_SALE` | Post Sale | Post sales to inventory (finalize transaction) |
| `VOID_SALE` | Void Sale | Void posted sales (requires manager override) |
| `REFUND_PAYMENT` | Refund Payment | Process payment refunds |
| `PROCESS_RETURN` | Process Return | Process product returns |
| `VIEW_SALES_REPORTS` | View Sales Reports | Access sales reports and analytics |

### REGISTERS

| Code | Name | Description |
|------|------|-------------|
| `CREATE_REGISTER` | Create Register | Create new POS registers/devices |
| `MANAGE_REGISTER` | Manage Registers | Create/edit/deactivate registers and settings |

### DOCUMENTS

| Code | Name | Description |
|------|------|-------------|
| `APPROVE_DOCUMENTS` | Approve Documents | Approve DRAFT documents (DRAFT → APPROVED) |
| `POST_DOCUMENTS` | Post Documents | Post documents to ledger (APPROVED → POSTED) |
| `VIEW_DOCUMENTS` | View Documents | View documents and their details |
| `CREATE_TRANSFERS` | Create Transfers | Create inter-store transfer documents |
| `CREATE_COUNTS` | Create Counts | Create physical inventory count documents |

### USERS

| Code | Name | Description |
|------|------|-------------|
| `VIEW_USERS` | View Users | View user accounts and roles |
| `CREATE_USER` | Create User | Create new user accounts |
| `EDIT_USER` | Edit User | Edit user account details |
| `ASSIGN_ROLES` | Assign Roles | Assign roles to users |
| `DEACTIVATE_USER` | Deactivate User | Deactivate user accounts |

### SYSTEM

| Code | Name | Description |
|------|------|-------------|
| `MANAGE_PRODUCTS` | Manage Products | Create, edit, and deactivate products |
| `MANAGE_IDENTIFIERS` | Manage Identifiers | Add/edit product identifiers (barcodes, SKUs) |
| `VIEW_AUDIT_LOG` | View Audit Log | Access security and audit logs |
| `VIEW_STORES` | View Stores | View store details and hierarchy |
| `MANAGE_STORES` | Manage Stores | Create and update stores and configuration |
| `SWITCH_STORE` | Switch Store | Switch between stores within the organization |
| `MANAGE_PERMISSIONS` | Manage Permissions | Grant/revoke permissions (admin only) |
| `SYSTEM_ADMIN` | System Administration | Full system access (admin only) |
| `CREATE_IMPORTS` | Create Imports | Create and manage import batches |
| `APPROVE_IMPORTS` | Approve Imports | Approve and post imports |
| `VIEW_ANALYTICS` | View Analytics | View analytics and reports |
| `VIEW_CROSS_STORE_ANALYTICS` | View Cross-Store Analytics | View org-wide analytics |
| `DEVELOPER_ACCESS` | Developer Access | Cross-organization developer access (PROTECTED) |

### TIMEKEEPING

| Code | Name | Description |
|------|------|-------------|
| `CLOCK_IN_OUT` | Clock In/Out | Clock in and out for shifts |
| `VIEW_TIMEKEEPING` | View Timekeeping | View time entries and reports |
| `APPROVE_TIME_CORRECTIONS` | Approve Time Corrections | Approve time clock corrections |
| `MANAGE_TIMEKEEPING` | Manage Timekeeping | Full timekeeping administration |

### COMMUNICATIONS

| Code | Name | Description |
|------|------|-------------|
| `VIEW_COMMUNICATIONS` | View Communications | View announcements, reminders, and tasks |
| `MANAGE_COMMUNICATIONS` | Manage Communications | Create and edit announcements and reminders |

### PROMOTIONS

| Code | Name | Description |
|------|------|-------------|
| `VIEW_PROMOTIONS` | View Promotions | View promotions and discounts |
| `MANAGE_PROMOTIONS` | Manage Promotions | Create, edit, and deactivate promotions |

### ORGANIZATION

| Code | Name | Description |
|------|------|-------------|
| `VIEW_ORGANIZATION` | View Organization | View organization details and structure |
| `MANAGE_ORGANIZATION` | Manage Organization | Organization-level administration |

### DEVICES

| Code | Name | Description |
|------|------|-------------|
| `VIEW_DEVICE_SETTINGS` | View Device Settings | View device configurations |
| `MANAGE_DEVICE_SETTINGS` | Manage Device Settings | Configure device-level settings |

---

## Default Role Bundles

### Admin (48 permissions)
All permissions except `DEVELOPER_ACCESS`.

### Developer (49 permissions)
All permissions including `DEVELOPER_ACCESS`. Requires `is_developer` flag on user model.

### Manager (39 permissions)
Operational management without system administration:
- All inventory, sales, register, and document operations
- User management (view, create, edit — no role assignment, no deactivation)
- Products, identifiers, audit log, stores, vendors
- Imports (create and approve)
- Analytics (single-store only — no `VIEW_CROSS_STORE_ANALYTICS`)
- Timekeeping (clock, view, approve corrections — no full management)
- Communications (view and manage)
- Promotions (view only — no management)
- Organization (view only)
- Devices (view and manage)
- **Excluded**: `ASSIGN_ROLES`, `DEACTIVATE_USER`, `SWITCH_STORE`, `MANAGE_PERMISSIONS`, `SYSTEM_ADMIN`, `VIEW_CROSS_STORE_ANALYTICS`, `MANAGE_TIMEKEEPING`, `MANAGE_PROMOTIONS`, `MANAGE_ORGANIZATION`

### Cashier (7 permissions)
Minimal POS operations:
- `VIEW_INVENTORY`, `CREATE_SALE`, `POST_SALE`, `PROCESS_RETURN`
- `CLOCK_IN_OUT`, `VIEW_COMMUNICATIONS`, `VIEW_PROMOTIONS`

---

## Override System

Per-user overrides allow granting or denying specific permissions independently of roles:
- **GRANT**: Adds a permission the user's roles don't provide
- **DENY**: Removes a permission the user's roles would normally provide
- **Protected**: `DEVELOPER_ACCESS` cannot be altered via overrides
- Overrides can be revoked (soft-delete with audit trail: who, when, reason)

Source: `backend/app/permissions/definitions.py`, `backend/app/permissions/roles.py`
