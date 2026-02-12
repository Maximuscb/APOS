# APOS 1.3 — Authorization Coverage Map

## Backend Route Coverage

Every protected endpoint uses `@require_auth` (sets `g.org_id`, `g.current_user`, `g.store_id`) plus one of:
- `@require_permission("CODE")` — requires specific permission
- `@require_any_permission("A", "B")` — requires any one of listed permissions
- `@require_all_permissions("A", "B")` — requires all listed permissions
- `@require_developer` — requires `is_developer` flag on user

Developers bypass all permission checks (except `@require_developer` which explicitly checks the flag).

### Auth Routes (`/api/auth/*`)

| Method | Endpoint | Auth | Permission |
|--------|----------|------|------------|
| POST | `/api/auth/login` | None | None |
| POST | `/api/auth/login-pin` | None | None |
| POST | `/api/auth/validate` | None | None |
| POST | `/api/auth/logout` | None | None |
| GET | `/api/auth/lockout-status/<id>` | None | None |
| POST | `/api/auth/set-pin` | `@require_auth` | None |
| DELETE | `/api/auth/delete` | `@require_auth` | None |
| GET | `/api/auth/has-pin` | `@require_auth` | None |

### Admin Routes (`/api/admin/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/admin/users` | `VIEW_USERS` |
| GET | `/api/admin/users/<id>` | `VIEW_USERS` |
| POST | `/api/admin/users` | `CREATE_USER` |
| PATCH | `/api/admin/users/<id>` | `EDIT_USER` |
| POST | `/api/admin/users/<id>/deactivate` | `DEACTIVATE_USER` |
| POST | `/api/admin/users/<id>/reactivate` | `DEACTIVATE_USER` |
| POST | `/api/admin/users/<id>/reset-password` | `EDIT_USER` |
| GET | `/api/admin/users/<id>/manager-stores` | any(`EDIT_USER`, `MANAGE_STORES`) |
| POST | `/api/admin/users/<id>/manager-stores` | any(`EDIT_USER`, `MANAGE_STORES`) |
| DELETE | `/api/admin/users/<id>/manager-stores/<sid>` | any(`EDIT_USER`, `MANAGE_STORES`) |
| GET | `/api/admin/roles` | `VIEW_USERS` |
| GET | `/api/admin/roles/<name>` | `VIEW_USERS` |
| POST | `/api/admin/roles` | `MANAGE_PERMISSIONS` |
| POST | `/api/admin/users/<id>/roles` | `ASSIGN_ROLES` |
| DELETE | `/api/admin/users/<id>/roles/<name>` | `ASSIGN_ROLES` |
| GET | `/api/admin/permissions` | `VIEW_USERS` |
| GET | `/api/admin/permissions/categories` | `VIEW_USERS` |
| POST | `/api/admin/roles/<name>/permissions` | `MANAGE_PERMISSIONS` |
| DELETE | `/api/admin/roles/<name>/permissions/<code>` | `MANAGE_PERMISSIONS` |
| GET | `/api/admin/users/<id>/permission-overrides` | `MANAGE_PERMISSIONS` |
| POST | `/api/admin/users/<id>/permission-overrides` | `MANAGE_PERMISSIONS` |
| DELETE | `/api/admin/users/<id>/permission-overrides/<code>` | `MANAGE_PERMISSIONS` |

### Developer Routes (`/api/developer/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/developer/organizations` | `@require_developer` |
| POST | `/api/developer/organizations` | `@require_developer` |
| POST | `/api/developer/switch-org` | `@require_developer` |
| GET | `/api/developer/status` | `@require_developer` |

### Sales Routes (`/api/sales/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| POST | `/api/sales/` | `CREATE_SALE` |
| POST | `/api/sales/<id>/lines` | `CREATE_SALE` |
| POST | `/api/sales/<id>/post` | `POST_SALE` |
| GET | `/api/sales/<id>` | `CREATE_SALE` |

### Payments Routes (`/api/payments/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| POST | `/api/payments/` | `CREATE_SALE` |
| POST | `/api/payments/<id>/void` | `VOID_SALE` |

### Returns Routes (`/api/returns/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| POST | `/api/returns/` | `PROCESS_RETURN` |

### Inventory Routes (`/api/inventory/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| POST | `/api/inventory/adjust` | `ADJUST_INVENTORY` |

### Products Routes (`/api/products/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/products/status` | auth only |
| GET | `/api/products` | `VIEW_INVENTORY` |
| POST | `/api/products` | `MANAGE_PRODUCTS` |

### Receives Routes (`/api/receives/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/receives` | `VIEW_INVENTORY` |
| POST | `/api/receives` | `RECEIVE_INVENTORY` |

### Transfers Routes (`/api/transfers/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| POST | `/api/transfers` | `CREATE_TRANSFERS` |

### Counts Routes (`/api/counts/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| POST | `/api/counts` | `CREATE_COUNTS` |

### Lifecycle Routes (`/api/lifecycle/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| POST | `/api/lifecycle/approve/<id>` | `APPROVE_DOCUMENTS` |
| POST | `/api/lifecycle/post/<id>` | `POST_DOCUMENTS` |
| GET | `/api/lifecycle/pending` | `APPROVE_DOCUMENTS` |
| GET | `/api/lifecycle/approved` | `POST_DOCUMENTS` |

### Documents Routes (`/api/documents/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/documents` | `VIEW_DOCUMENTS` |
| GET | `/api/documents/<type>/<id>` | `VIEW_DOCUMENTS` |

### Registers Routes (`/api/registers/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| POST | `/api/registers/` | `MANAGE_REGISTER` |
| GET | `/api/registers/<id>` | auth only |

### Stores Routes (`/api/stores/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/stores` | `VIEW_STORES` |
| POST | `/api/stores` | `MANAGE_STORES` |
| GET | `/api/stores/<id>` | `VIEW_STORES` |
| PUT | `/api/stores/<id>` | `MANAGE_STORES` |
| GET | `/api/stores/<id>/configs` | `VIEW_STORES` |
| PUT | `/api/stores/<id>/configs` | `MANAGE_STORES` |
| GET | `/api/stores/<id>/tree` | `VIEW_STORES` |

### Analytics Routes (`/api/analytics/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/analytics/sales-trends` | `VIEW_ANALYTICS` |
| GET | `/api/analytics/inventory-valuation` | `VIEW_ANALYTICS` |
| GET | `/api/analytics/margin-cogs` | `VIEW_ANALYTICS` |
| GET | `/api/analytics/slow-stock` | `VIEW_ANALYTICS` |

### Reports Routes (`/api/reports/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/reports/sales` | `VIEW_SALES_REPORTS` |
| GET | `/api/reports/sales-summary` | `VIEW_SALES_REPORTS` |
| GET | `/api/reports/sales-by-time` | `VIEW_SALES_REPORTS` |
| GET | `/api/reports/sales-by-employee` | `VIEW_SALES_REPORTS` |

### Timekeeping Routes (`/api/timekeeping/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| POST | `/api/timekeeping/clock-in` | `CLOCK_IN_OUT` |
| POST | `/api/timekeeping/clock-out` | `CLOCK_IN_OUT` |
| POST | `/api/timekeeping/break/start` | `CLOCK_IN_OUT` |
| POST | `/api/timekeeping/break/end` | `CLOCK_IN_OUT` |
| GET | `/api/timekeeping/entries` | any(`VIEW_TIMEKEEPING`, `MANAGE_TIMEKEEPING`) |
| PATCH | `/api/timekeeping/entries/<id>` | `MANAGE_TIMEKEEPING` |
| POST | `/api/timekeeping/corrections` | `CLOCK_IN_OUT` |
| POST | `/api/timekeeping/corrections/<id>/approve` | `APPROVE_TIME_CORRECTIONS` |

### Imports Routes (`/api/imports/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| POST | `/api/imports/batches` | `CREATE_IMPORTS` |
| POST | `/api/imports/batches/<id>/upload` | `CREATE_IMPORTS` |

### Communications Routes (`/api/communications/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/communications/active` | auth only |
| GET | `/api/communications/notifications` | any(`VIEW_COMMUNICATIONS`, `MANAGE_COMMUNICATIONS`) |
| POST | `/api/communications/notifications` | `MANAGE_COMMUNICATIONS` |

### Promotions Routes (`/api/promotions/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/promotions` | any(`VIEW_PROMOTIONS`, `MANAGE_PROMOTIONS`) |
| POST | `/api/promotions` | `MANAGE_PROMOTIONS` |
| PATCH | `/api/promotions/<id>` | `MANAGE_PROMOTIONS` |
| GET | `/api/promotions/active` | auth only |

### Vendors Routes (`/api/vendors/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/vendors` | `VIEW_VENDORS` |
| POST | `/api/vendors` | `MANAGE_VENDORS` |

### Identifiers Routes (`/api/identifiers/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/identifiers/lookup/<value>` | `VIEW_INVENTORY` |
| POST | `/api/identifiers/` | `MANAGE_IDENTIFIERS` |

### Settings Routes

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/organizations/<id>/settings` | any(`MANAGE_ORGANIZATION`, `VIEW_ORGANIZATION`) |
| PUT | `/api/organizations/<id>/settings` | `MANAGE_ORGANIZATION` |
| GET | `/api/devices/<id>/settings` | any(`VIEW_DEVICE_SETTINGS`, `MANAGE_DEVICE_SETTINGS`) |
| PUT | `/api/devices/<id>/settings` | `MANAGE_DEVICE_SETTINGS` |

### Ledger Routes (`/api/ledger/*`)

| Method | Endpoint | Permission |
|--------|----------|------------|
| GET | `/api/ledger` | `VIEW_AUDIT_LOG` |

### System Routes (Public)

| Method | Endpoint | Auth | Permission |
|--------|----------|------|------------|
| GET | `/health` | None | None |
| GET | `/health/session` | None | None |
| GET | `/version` | None | None |

---

## Frontend Route Coverage

| Frontend Route | `RequirePermission anyOf` | SidebarNav Permissions |
|---------------|--------------------------|----------------------|
| `/sales` | `CREATE_SALE` | — |
| `/inventory` | `VIEW_INVENTORY` | — |
| `/operations/dashboard` | (open) | (always visible) |
| `/operations/analytics` | `VIEW_ANALYTICS` | `VIEW_ANALYTICS` |
| `/operations/devices` | `CREATE_SALE`, `MANAGE_REGISTER` | `CREATE_SALE`, `MANAGE_REGISTER` |
| `/operations/reports` | `VIEW_DOCUMENTS` | `VIEW_DOCUMENTS` |
| `/operations/communications` | `VIEW_COMMUNICATIONS`, `MANAGE_COMMUNICATIONS` | `VIEW_COMMUNICATIONS`, `MANAGE_COMMUNICATIONS` |
| `/operations/promotions` | `VIEW_PROMOTIONS`, `MANAGE_PROMOTIONS` | `VIEW_PROMOTIONS`, `MANAGE_PROMOTIONS` |
| `/operations/services` | `CREATE_IMPORTS` | `CREATE_IMPORTS` |
| `/operations/timekeeping` | `VIEW_TIMEKEEPING`, `MANAGE_TIMEKEEPING` | `VIEW_TIMEKEEPING`, `MANAGE_TIMEKEEPING` |
| `/operations/vendors` | `VIEW_VENDORS`, `MANAGE_VENDORS` | `VIEW_VENDORS`, `MANAGE_VENDORS` |
| `/operations/users` | `VIEW_USERS`, `CREATE_USER`, `EDIT_USER`, `ASSIGN_ROLES`, `DEACTIVATE_USER` | same |
| `/operations/settings` | `VIEW_STORES`, `MANAGE_STORES` | `VIEW_STORES`, `MANAGE_STORES` |
| `/operations/developer` | `isDeveloper` (page-level) | `isDeveloper` (special) |

---

## Developer Tools Lockdown

| Tool | Backend Gate | Frontend Gate | Production Kill Switch |
|------|-------------|---------------|----------------------|
| Developer Dashboard | `@require_developer` | `isDeveloper` check returns "Access Denied" card | `APOS_DEVELOPER_TOOLS=false` env var |
| Org creation | `@require_developer` | Only in DeveloperPage | Same |
| Org switching | `@require_developer` | Only in DeveloperPage | Same |
| Debug endpoints | `debug.py` is empty | N/A | N/A |

The `is_developer` flag lives on the User model and cannot be set via API — it must be set directly in the database.
`DEVELOPER_ACCESS` permission is protected and cannot be granted via user overrides.
