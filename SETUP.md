Test Change
# APOS Setup & CLI Guide

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

**Default Credentials:**
```
admin    → admin@apos.local    / password123
manager  → manager@apos.local  / password123
cashier  → cashier@apos.local  / password123
```

⚠️ **SECURITY:** Change these passwords immediately in production!

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
**Interactive user creation**

```bash
FLASK_APP=wsgi.py python -m flask create-user
```

Prompts for:
- Username
- Email
- Password (hidden input)
- Role (admin/manager/cashier)

Example:
```
Username: john
Email: john@example.com
Password: ********
Repeat for confirmation: ********
Role (admin, manager, cashier): manager
✅ Created user: john (john@example.com) with role 'manager'
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
```

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

**Before deploying to production:**

1. **Change all default passwords**
   ```bash
   FLASK_APP=wsgi.py python -m flask create-user
   # Create new admin with strong password
   ```

2. **Replace stub auth with bcrypt**
   - Update `app/services/auth_service.py`
   - Use `bcrypt.hashpw()` for password hashing
   - Implement proper session management

3. **Use PostgreSQL instead of SQLite**
   ```bash
   export DATABASE_URL=postgresql://user:pass@localhost/apos
   ```

4. **Enable HTTPS/TLS**

5. **Set up proper backup schedule**

6. **Review all TODO/STUB comments in code**

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
