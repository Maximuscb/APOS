Test Change
# APOS Setup & CLI Guide

**Production-Ready Authentication**
**Role-Based Permissions**

This guide covers setup, CLI commands, security, and permission management for APOS.

## Quick Start

### 1. Initial Setup

```bash
# Backend setup
cd backend
pip install -r requirements.txt

# Create database and run migrations
FLASK_APP=wsgi.py python -m flask db upgrade

# Initialize system (creates roles + default users + store)
FLASK_APP=wsgi.py python -m flask init-system
```

### 2. Start Backend

```bash
cd backend
FLASK_APP=wsgi.py python -m flask run
```

### 3. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit: **http://localhost:5173**

---

## Security & Authentication ()

### Password Requirements

All passwords must meet these requirements:
- **Minimum 8 characters**
- At least **one uppercase** letter (A-Z)
- At least **one lowercase** letter (a-z)
- At least **one digit** (0-9)
- At least **one special character** (!@#$%^&*(),.?":{}|<>)

Example valid passwords:
- `Password123!`
- `Secure@Pass1`
- `MyP@ssw0rd`

### Password Hashing

- **bcrypt** with cost factor 12
- Salt automatically generated per-password
- Timing-safe comparison prevents attacks
- Legacy `STUB_HASH_` passwords still supported during migration

### Session Tokens

- **64-character** cryptographically secure tokens
- Tokens hashed with **SHA-256** before storage
- **24-hour absolute timeout** (maximum session length)
- **2-hour idle timeout** (auto-revoke if inactive)
- Revocable on logout or security events
- Tracks IP address and user agent for monitoring

### API Authentication

Protected routes require `Authorization` header:

```bash
Authorization: Bearer <token>
```

Obtain token via `POST /api/auth/login`:

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "Password123!"}'
```

Response includes `token` field for subsequent requests.

---

## Role-Based Permissions ()

### Permission System

APOS implements granular RBAC with **22 permissions** across **5 categories**:

**INVENTORY (5 permissions):**
- VIEW_INVENTORY - View inventory quantities and transactions
- RECEIVE_INVENTORY - Create RECEIVE transactions
- ADJUST_INVENTORY - Create ADJUST transactions
- APPROVE_ADJUSTMENTS - Approve DRAFT adjustments
- VIEW_COGS - View cost calculations

**SALES (5 permissions):**
- CREATE_SALE - Create new sales documents (POS access)
- POST_SALE - Post sales to inventory
- VOID_SALE - Void posted sales
- PROCESS_RETURN - Process product returns
- VIEW_SALES_REPORTS - Access sales reports

**DOCUMENTS (2 permissions):**
- APPROVE_DOCUMENTS - DRAFT → APPROVED
- POST_DOCUMENTS - APPROVED → POSTED

**USERS (5 permissions):**
- VIEW_USERS - View user accounts and roles
- CREATE_USER - Create new user accounts
- EDIT_USER - Edit user details
- ASSIGN_ROLES - Assign roles to users
- DEACTIVATE_USER - Deactivate user accounts

**SYSTEM (5 permissions):**
- MANAGE_PRODUCTS - Create/edit/deactivate products
- MANAGE_IDENTIFIERS - Add/edit barcodes, SKUs
- VIEW_AUDIT_LOG - Access security logs
- MANAGE_PERMISSIONS - Grant/revoke permissions
- SYSTEM_ADMIN - Full system access

### Default Role Permissions

| Permission | Admin | Manager | Cashier |
|------------|-------|---------|---------|
| **All 22 permissions** | ✅ | | |
| **Most permissions (18)** | ✅ | ✅ | |
| **POS operations only (4)** | ✅ | ✅ | ✅ |

**Admin:** Full access (22 permissions)
**Manager:** Management functions, no system admin (18 permissions)
**Cashier:** POS only - VIEW_INVENTORY, CREATE_SALE, POST_SALE, PROCESS_RETURN (4 permissions)

### Security Event Logging

All permission checks are logged to `security_events` table:
- **PERMISSION_GRANTED** - User has required permission
- **PERMISSION_DENIED** - User lacks permission (403 response)
- Includes: user_id, resource, action, IP address, user agent
- Immutable audit trail for compliance

### Permission Management CLI

#### `flask init-permissions`
Initialize permission system (creates all permissions and assigns defaults):

```bash
FLASK_APP=wsgi.py python -m flask init-permissions
```

Automatically run by `flask init-system`.

#### `flask list-permissions`
List all permissions:

```bash
# All permissions
FLASK_APP=wsgi.py python -m flask list-permissions

# Permissions for specific role
FLASK_APP=wsgi.py python -m flask list-permissions --role cashier

# Permissions in category
FLASK_APP=wsgi.py python -m flask list-permissions --category SALES
```

#### `flask grant-permission`
Grant permission to role:

```bash
FLASK_APP=wsgi.py python -m flask grant-permission cashier VOID_SALE
```

#### `flask revoke-permission`
Revoke permission from role:

```bash
FLASK_APP=wsgi.py python -m flask revoke-permission cashier VOID_SALE
```

#### `flask check-permission`
Check if user has permission:

```bash
FLASK_APP=wsgi.py python -m flask check-permission admin SYSTEM_ADMIN
# Output: ✅ User 'admin' HAS permission 'SYSTEM_ADMIN'
```

### API Error Responses

**401 Unauthorized** - Missing or invalid authentication token
```json
{
  "error": "Authentication required"
}
```

**403 Forbidden** - Valid auth but insufficient permission
```json
{
  "error": "Permission denied",
  "required_permission": "APPROVE_ADJUSTMENTS",
  "message": "Permission denied: APPROVE_ADJUSTMENTS"
}
```

---

## Register Management ()

### Overview

APOS tracks POS registers (terminals) and cashier shifts for accountability and audit trails.

**Key Concepts:**
- **Register:** Physical POS terminal (e.g., "Front Counter", "Drive-Thru")
- **Register Session:** Cashier shift on a register (opening to closing)
- **Cash Drawer Events:** Audit trail of all drawer opens (sales, no-sales, drops)
- **Variance Tracking:** Compares expected vs actual cash at shift close

### Register Lifecycle

1. **Create Register** (admin/manager)
   - Assign register number (e.g., REG-01)
   - Set location and device ID
   - Only done once per physical terminal

2. **Open Shift** (cashier)
   - Cashier signs in to register
   - Records opening cash amount
   - Creates RegisterSession (status: OPEN)
   - Logs SHIFT_OPEN event

3. **During Shift**
   - Sales automatically linked to register and session
   - No-sale drawer opens require manager approval
   - Cash drops (remove excess cash) require manager approval
   - All events logged to cash_drawer_events

4. **Close Shift** (cashier)
   - Count closing cash
   - System calculates variance (expected vs actual)
   - Session becomes CLOSED (immutable)
   - Logs SHIFT_CLOSE event

### Cash Drawer Event Types

- **SHIFT_OPEN:** Drawer opened at shift start
- **SALE:** Drawer opened for sale transaction (automatic)
- **NO_SALE:** Drawer opened without sale (requires manager approval + reason)
- **CASH_DROP:** Remove excess cash to safe (requires manager approval + reason)
- **SHIFT_CLOSE:** Final cash count at shift end

### Register Management CLI

#### `flask create-register`
Create a new POS register:

```bash
FLASK_APP=wsgi.py python -m flask create-register \
  --store-id 1 \
  --number "REG-01" \
  --name "Front Counter Register 1" \
  --location "Main Floor"
```

Optional: `--device-id` for hardware identifier (MAC address, serial number, etc.)

#### `flask list-registers`
List all registers:

```bash
# All active registers
FLASK_APP=wsgi.py python -m flask list-registers

# Specific store
FLASK_APP=wsgi.py python -m flask list-registers --store-id 1

# Include inactive
FLASK_APP=wsgi.py python -m flask list-registers --all
```

Output:
```
====================================================================================================
ID    Number       Name                      Location             Active   Status
====================================================================================================
1     REG-01       Front Counter Register 1  Main Floor           Yes      OPEN
2     REG-02       Drive-Thru Register       Outside              Yes      CLOSED
====================================================================================================
```

#### `flask open-shift`
Open a new shift on a register:

```bash
FLASK_APP=wsgi.py python -m flask open-shift \
  --register-id 1 \
  --username cashier \
  --opening-cash 100.00
```

Output:
```
✅ Shift opened successfully!
   Session ID: 1
   Register ID: 1
   User: cashier
   Opening Cash: $100.00
   Opened At: 2026-01-14 17:43:00
```

**Rules:**
- Only one shift can be open per register at a time
- Attempting to open second shift returns error
- Must close current shift before opening new one

#### `flask close-shift`
Close a shift and calculate variance:

```bash
FLASK_APP=wsgi.py python -m flask close-shift \
  --session-id 1 \
  --closing-cash 125.50 \
  --notes "Good shift, no issues"
```

Output:
```
✅ Shift closed successfully!
   Session ID: 1
   Opening Cash: $100.00
   Expected Cash: $120.00
   Closing Cash: $125.50
   Variance: $+5.50
   ⚠️  OVER by $5.50
   Notes: Good shift, no issues
```

**Variance Calculation:**
- `variance = closing_cash - expected_cash`
- Positive variance: Cash OVER (extra money in drawer)
- Negative variance: Cash SHORT (missing money)
- Zero variance: Perfectly balanced

**Immutability:**
- Once closed, sessions cannot be reopened or modified
- Provides accurate historical accountability

#### `flask list-sessions`
List register sessions:

```bash
# All recent sessions (last 20)
FLASK_APP=wsgi.py python -m flask list-sessions

# Specific register
FLASK_APP=wsgi.py python -m flask list-sessions --register-id 1

# Only open sessions
FLASK_APP=wsgi.py python -m flask list-sessions --status OPEN

# More results
FLASK_APP=wsgi.py python -m flask list-sessions --limit 50
```

Output:
```
========================================================================================================================
ID    Register     User            Status   Opened               Variance     Notes
========================================================================================================================
2     REG-01       cashier         CLOSED   2026-01-14 17:43:00  $+5.50       Good shift, no issues
1     REG-01       manager         CLOSED   2026-01-14 08:00:00  $-2.00       Short $2
========================================================================================================================
```

### Register Management API

All register routes require authentication (`Authorization: Bearer <token>`).

#### Create Register
```http
POST /api/registers
Content-Type: application/json
Authorization: Bearer <token>

{
  "store_id": 1,
  "register_number": "REG-01",
  "name": "Front Counter Register 1",
  "location": "Main Floor",
  "device_id": "MAC-00-11-22-33-44-55"
}
```

Requires: `MANAGE_REGISTER` permission (admin, manager)

#### List Registers
```http
GET /api/registers?store_id=1
Authorization: Bearer <token>
```

Requires: `CREATE_SALE` permission (admin, manager, cashier)

#### Get Register Details
```http
GET /api/registers/1
Authorization: Bearer <token>
```

Returns register with current session status:
```json
{
  "id": 1,
  "register_number": "REG-01",
  "name": "Front Counter Register 1",
  "location": "Main Floor",
  "is_active": true,
  "current_session": {
    "id": 5,
    "status": "OPEN",
    "user_id": 3,
    "opening_cash_cents": 10000,
    "opened_at": "2026-01-14T17:43:00Z"
  }
}
```

#### Open Shift
```http
POST /api/registers/1/shifts/open
Content-Type: application/json
Authorization: Bearer <token>

{
  "opening_cash_cents": 10000
}
```

Requires: `CREATE_SALE` permission
Returns: `201 Created` with session details
Error: `400 Bad Request` if register already has open shift

#### Close Shift
```http
POST /api/registers/sessions/5/close
Content-Type: application/json
Authorization: Bearer <token>

{
  "closing_cash_cents": 12550,
  "notes": "Good shift"
}
```

Requires: `CREATE_SALE` permission
Returns: `200 OK` with closed session and variance

#### No-Sale Drawer Open
```http
POST /api/registers/sessions/5/drawer/no-sale
Content-Type: application/json
Authorization: Bearer <token>

{
  "approved_by_user_id": 2,
  "reason": "Customer needed change for $20"
}
```

Requires:
- `CREATE_SALE` permission (cashier can request)
- Manager approval (manager user ID required)
- Reason must be provided

Creates audit trail event (event_type: NO_SALE)

#### Cash Drop
```http
POST /api/registers/sessions/5/drawer/cash-drop
Content-Type: application/json
Authorization: Bearer <token>

{
  "amount_cents": 5000,
  "approved_by_user_id": 2,
  "reason": "Safe drop - drawer over $200"
}
```

Requires:
- `CREATE_SALE` permission
- Manager approval
- Positive amount

Reduces `expected_cash_cents` by drop amount
Creates audit trail event (event_type: CASH_DROP)

#### List Drawer Events
```http
GET /api/registers/1/events?event_type=NO_SALE&limit=100
Authorization: Bearer <token>
```

Query parameters:
- `event_type`: Filter by type (SHIFT_OPEN, SALE, NO_SALE, CASH_DROP, SHIFT_CLOSE)
- `start_date`: Filter after date (ISO 8601)
- `end_date`: Filter before date (ISO 8601)
- `limit`: Max events (default: 100)

### Best Practices

**Security:**
- No-sale drawer opens always require manager approval
- Cash drops always require manager approval
- All events logged with user_id, timestamps, and reasons
- Sessions are immutable once closed

**Operations:**
- Open shifts at start of cashier's shift
- Perform cash drops when drawer exceeds $200 (adjust per store policy)
- Count closing cash carefully to minimize variance
- Document reasons for no-sale opens clearly
- Close shifts promptly at end of cashier's shift

**Accountability:**
- Each session tracks one cashier's accountability period
- Variance tracking identifies cash handling issues
- Audit trail helps investigate discrepancies
- Manager approvals create accountability chain

**Reporting:**
- Review variances daily
- Investigate large or frequent shortages
- Monitor no-sale events for suspicious patterns
- Track cash drop compliance

---

## CLI Commands

### System Initialization

#### `flask init-system`
**Initialize complete APOS system**

Creates:
- Default store (Main Store)
- Roles: admin, manager, cashier
- Default users with roles

```bash
FLASK_APP=wsgi.py python -m flask init-system
```

**Default Credentials ():**
```
admin    → admin@apos.local    / Password123!
manager  → manager@apos.local  / Password123!
cashier  → cashier@apos.local  / Password123!
```

⚠️ **SECURITY WARNINGS:**
- Passwords are now **securely hashed with bcrypt**
- **Change all passwords immediately in production!**
- Default passwords meet requirements but are publicly documented
- Use `flask create-user` to create users with unique passwords

---

#### `flask init-roles`
**Create default roles only**

```bash
FLASK_APP=wsgi.py python -m flask init-roles
```

Creates: admin, manager, cashier roles

---

### User Management

#### `flask create-user`
**Interactive user creation with password validation**

```bash
FLASK_APP=wsgi.py python -m flask create-user
```

Prompts for:
- Username
- Email
- Password (hidden input, must meet requirements)
- Role (admin/manager/cashier)

Example:
```
Username: john
Email: john@example.com
Password: ********
Repeat for confirmation: ********
Role (admin, manager, cashier): manager
✅ Created user: john (john@example.com) with role 'manager'
🔒 Password securely hashed with bcrypt
```

**Password validation errors:**
```
❌ Password validation failed: Password must be at least 8 characters long
Requirements: 8+ chars, uppercase, lowercase, digit, special char
```

---

#### `flask list-users`
**List all users with their roles**

```bash
FLASK_APP=wsgi.py python -m flask list-users
```

Output:
```
================================================================================
ID    Username             Email                          Active   Roles
================================================================================
1     admin                admin@apos.local               Yes      admin
2     manager              manager@apos.local             Yes      manager
3     cashier              cashier@apos.local             Yes      cashier
================================================================================
```

---

### Database Management

#### `flask db upgrade`
**Apply all pending migrations**

```bash
FLASK_APP=wsgi.py python -m flask db upgrade
```

#### `flask db migrate -m "description"`
**Generate new migration after model changes**

```bash
FLASK_APP=wsgi.py python -m flask db migrate -m "add new field"
```

#### `flask reset-db`
**DANGER: Drop and recreate all tables**

```bash
# Interactive (asks for confirmation)
FLASK_APP=wsgi.py python -m flask reset-db

# Skip confirmation
FLASK_APP=wsgi.py python -m flask reset-db --yes
```

⚠️ **This deletes ALL data!**

---

## Complete Fresh Install

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Reset and initialize database
FLASK_APP=wsgi.py python -m flask reset-db --yes
FLASK_APP=wsgi.py python -m flask db upgrade
FLASK_APP=wsgi.py python -m flask init-system

# 3. Verify setup
FLASK_APP=wsgi.py python -m flask list-users

# 4. Run tests
python Audit.py
python LifecycleAudit.py
python AuthenticationAudit.py
```

---

## Testing

### Run All Tests

```bash
cd backend

# Core inventory and COGS tests
python Audit.py

# Document lifecycle tests
python LifecycleAudit.py

# Authentication security tests
python AuthenticationAudit.py
```

### Authentication Tests ()

`AuthenticationAudit.py` verifies:
- Password strength validation
- bcrypt password hashing
- User creation with bcrypt
- Session token generation
- Session lifecycle (create, validate, revoke)
- Session timeouts (absolute and idle)
- Revoke all sessions
- Complete login/logout flow

All tests must pass before production deployment.

---

## Database Location

**SQLite Database:** `backend/instance/apos.sqlite3`

To backup:
```bash
cp backend/instance/apos.sqlite3 backend/instance/apos.backup.sqlite3
```

To restore:
```bash
cp backend/instance/apos.backup.sqlite3 backend/instance/apos.sqlite3
```

---

## Environment Variables

```bash
# Set Flask app
export FLASK_APP=wsgi.py

# Enable debug mode (development only)
export FLASK_DEBUG=1

# Database URL (optional, defaults to SQLite)
export DATABASE_URL=sqlite:///instance/apos.sqlite3
```

---

## Troubleshooting

### "No module named flask"
```bash
cd backend
pip install -r requirements.txt
```

### "Target database is not up to date"
```bash
FLASK_APP=wsgi.py python -m flask db upgrade
```

### "No store found"
```bash
FLASK_APP=wsgi.py python -m flask init-system
```

### Reset everything
```bash
rm backend/instance/apos.sqlite3
FLASK_APP=wsgi.py python -m flask db upgrade
FLASK_APP=wsgi.py python -m flask init-system
```

---

## Testing

```bash
# Run all tests
cd backend
python Audit.py           # Original tests
python LifecycleAudit.py  # Lifecycle tests

# Tests should output:
# ================================================================================
# ALL TESTS PASSED
# ================================================================================
```

---

## Production Deployment

### ✅ Security Complete

The following are **now implemented** in - ✅ bcrypt password hashing (cost factor 12)
- ✅ Strong password validation
- ✅ Secure session token management
- ✅ Session timeouts (24-hour absolute, 2-hour idle)
- ✅ Explicit logout and revocation

### 🔒 Pre-Production Security Checklist

**Critical (Must Do):**

- [ ] **Change all default passwords**
  ```bash
  # DO NOT use Password123! in production
  FLASK_APP=wsgi.py python -m flask create-user
  ```

- [ ] **Run all tests and verify they pass**
  ```bash
  python Audit.py
  python LifecycleAudit.py
  python AuthenticationAudit.py
  ```

- [ ] **Enable HTTPS/TLS** (session tokens sent in Authorization header)
  - Use reverse proxy (nginx, Apache) with SSL certificate
  - Redirect all HTTP to HTTPS
  - Set `Secure` flag on cookies if used

- [ ] **Review session timeout values** (in `session_service.py`)
  - Default: 24hr absolute, 2hr idle
  - Adjust based on security requirements

- [ ] **Set up database backups**
  ```bash
  # Example: Daily backup
  0 2 * * * cp /path/to/apos.sqlite3 /backups/apos-$(date +\%Y\%m\%d).sqlite3
  ```

- [ ] **Configure production database**
  ```bash
  # Use PostgreSQL for production
  export DATABASE_URL=postgresql://user:pass@localhost/apos
  FLASK_APP=wsgi.py python -m flask db upgrade
  ```

- [ ] **Disable Flask debug mode**
  ```bash
  export FLASK_DEBUG=0
  # Or remove FLASK_DEBUG variable entirely
  ```

- [ ] **Set up session cleanup cron job**
  ```python
  # Add to Flask CLI or cron:
  # Daily cleanup of expired sessions (30+ days old)
  from app.services.session_service import cleanup_expired_sessions
  cleanup_expired_sessions()
  ```

- [ ] **Configure CORS properly** (if frontend on different domain)
  - Whitelist only your frontend domain
  - Do not use `*` wildcard in production

**Recommended:**

- [ ] **Set up monitoring and alerting**
  - Failed login attempts
  - Session revocations
  - Password validation failures

- [ ] **Enable rate limiting** (prevent brute force)
  - Login endpoint: 5 attempts per minute per IP
  - Token validation: 60 requests per minute per token

- [ ] **Review and rotate secrets**
  - Database credentials
  - Flask SECRET_KEY
  - API keys (if any)

- [ ] **Set up audit log review process**
  - Review `session_tokens` table for suspicious activity
  - Monitor `revoked_reason` field for security events

- [ ] **Document password change policy**
  - Force password change every 90 days?
  - Notify users of password resets

**Future Enhancements ():**

- [ ] Implement role-based permissions enforcement
- [ ] Add manager override workflows
- [ ] Implement "remember me" functionality
- [ ] Add account lockout after N failed attempts
- [ ] Implement password reset via email
- [ ] Add two-factor authentication (2FA)

### Migration from Stub Auth

If you have existing users with `STUB_HASH_` passwords:

1. **Legacy passwords still work** (backwards compatibility)
2. Users can login with old passwords
3. **Force password reset** for all users:
   ```python
   # In Flask shell:
   from app.services.session_service import revoke_all_user_sessions
   from app.models import User
   users = User.query.all()
   for user in users:
       revoke_all_user_sessions(user.id, "Security upgrade - password reset required")
   ```

4. Users create new passwords meeting requirements
5. New passwords automatically use bcrypt

---

## Quick Reference

```bash
# Start backend
cd backend && FLASK_APP=wsgi.py python -m flask run

# Start frontend
cd frontend && npm run dev

# Initialize system
cd backend && FLASK_APP=wsgi.py python -m flask init-system

# User Management
cd backend && FLASK_APP=wsgi.py python -m flask list-users
cd backend && FLASK_APP=wsgi.py python -m flask create-user

# Permission Management ()
cd backend && FLASK_APP=wsgi.py python -m flask list-permissions
cd backend && FLASK_APP=wsgi.py python -m flask check-permission admin SYSTEM_ADMIN

# Register Management ()
cd backend && FLASK_APP=wsgi.py python -m flask create-register --store-id 1 --number "REG-01" --name "Front Counter"
cd backend && FLASK_APP=wsgi.py python -m flask list-registers
cd backend && FLASK_APP=wsgi.py python -m flask open-shift --register-id 1 --username cashier --opening-cash 100.00
cd backend && FLASK_APP=wsgi.py python -m flask close-shift --session-id 1 --closing-cash 125.50
cd backend && FLASK_APP=wsgi.py python -m flask list-sessions

# Run Tests
cd backend && python Audit.py
cd backend && python PermissionAudit.py
cd backend && python RegisterTests.py
```
