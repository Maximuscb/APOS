Test Change
# APOS Setup & CLI Guide

**Phase 6: Production-Ready Authentication**

This guide covers setup, CLI commands, and security requirements for APOS.

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

## Security & Authentication (Phase 6)

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

**Default Credentials (Phase 6):**
```
admin    → admin@apos.local    / Password123!
manager  → manager@apos.local  / Password123!
cashier  → cashier@apos.local  / Password123!
```

⚠️ **SECURITY WARNINGS:**
- Passwords are now **securely hashed with bcrypt**
- **Change all passwords immediately in production!**
- Default passwords meet Phase 6 requirements but are publicly documented
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

# Phase 1-3: Core inventory and COGS tests
python Audit.py

# Phase 5: Document lifecycle tests
python LifecycleAudit.py

# Phase 6: Authentication security tests
python AuthenticationAudit.py
```

### Authentication Tests (Phase 6)

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

### ✅ Phase 6 Security Complete

The following are **now implemented** in Phase 6:
- ✅ bcrypt password hashing (cost factor 12)
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

**Future Enhancements (Phase 7+):**

- [ ] Implement role-based permissions enforcement
- [ ] Add manager override workflows
- [ ] Implement "remember me" functionality
- [ ] Add account lockout after N failed attempts
- [ ] Implement password reset via email
- [ ] Add two-factor authentication (2FA)

### Migration from Phase 4 Stub Auth

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

4. Users create new passwords meeting Phase 6 requirements
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

# List users
cd backend && FLASK_APP=wsgi.py python -m flask list-users

# Create user
cd backend && FLASK_APP=wsgi.py python -m flask create-user

# Run tests
cd backend && python Audit.py
```
