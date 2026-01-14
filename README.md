Test Change
# APOS — Advanced Point-of-Sale System

**Backend-authoritative, ledger-driven retail platform**

---

## 1. What This Project Is (and Is Not)

**APOS is infrastructure, not an app.**

It is a deliberately slow-moving, correctness-first point-of-sale platform designed to survive **years of feature accretion without rewrites**. The system prioritizes:

* Auditability over convenience
* Determinism over cleverness
* Append-only ledgers over mutable state
* Backend authority over frontend logic

This is **not**:

* A demo
* An MVP
* A UI-driven experiment
* A frontend-heavy application
* A payment app with inventory bolted on

AI is explicitly **last**, approval-gated, and non-authoritative.

---

## 2. Core Architectural Principles (Non-Negotiable)

### Backend Authority (Hard Rule)

All business logic lives on the backend.

The frontend:

* Sends user intent
* Renders backend responses
* Formats values for display only (cents → dollars, UTC → local time)

The frontend **never**:

* Computes prices, taxes, costs, or inventory
* Enforces business rules
* Makes decisions

### Ledger-First Design (Hard Rule)

All inventory and financial state is **derived from append-only ledgers**.

There are:

* No mutable “on hand” fields
* No mutable balances
* No silent corrections

Corrections happen via **new ledger events**, never updates.

### Money Model (Locked)

* All monetary values stored and transmitted as **integer cents**
* Backend performs **all arithmetic**
* Frontend formats for display only

### Time Model (Locked)

* Canonical internal representation: **UTC-naive `datetime`**
* API accepts ISO-8601 with `Z` or offsets
* API returns ISO-8601 `Z`
* Frontend converts to local time for display only
* **As-of semantics are inclusive**: `occurred_at <= as_of`

### Determinism & Auditability

* Primary keys are immutable and never reused
* Human-readable document numbers exist **in addition** to internal IDs
* Every state-changing action is attributable to a user, device, register, and time
* “Why is X true?” must always be answerable from the ledger

---

## 3. Current Technology Stack

### Backend

* Python 3.11+
* Flask (app factory pattern only)
* Flask-SQLAlchemy
* Flask-Migrate (Alembic)
* SQLite for development (replaceable later)
* Blueprint routing
* Service-layer architecture
* Centralized validation

### Frontend

* Vite
* React
* TypeScript
* No UI frameworks (no Tailwind, no shadcn)
* Single long-lived dashboard (not page-oriented)
* Tablet-first layouts (Android compatibility is a requirement)

---

## 4. Backend Architecture Overview

```
backend/
├── app/
│   ├── __init__.py        # create_app(), blueprint registration
│   ├── config.py
│   ├── extensions.py     # db, migrate
│   ├── models.py         # Product, InventoryTransaction, MasterLedgerEvent, etc.
│   ├── validation.py     # centralized, model-driven validation
│   ├── time_utils.py     # UTC normalization, ISO parsing/serialization
│   ├── routes/
│   │   ├── system.py
│   │   ├── products.py
│   │   ├── inventory.py
│   │   └── ledger.py
│   └── services/
│       ├── products_service.py
│       ├── inventory_service.py
│       └── ledger_service.py
├── instance/
│   └── apos.sqlite3
├── migrations/
└── wsgi.py
```

### Service Layer Rules

Routes:

* Parse input
* Validate input
* Call a service

Services:

* Enforce invariants
* Perform database work
* Append ledger events
* Never leak unhandled exceptions

Models:

* Expose `.to_dict()` only
* Never embed business logic

---

## 5. Inventory & Cost Accounting (Implemented Core)

### Inventory Ledger (Non-Negotiable)

Inventory is managed via an append-only `InventoryTransaction` ledger.

Event types include:

* RECEIVE (stock in)
* SALE (stock out)
* ADJUST (manual correction)
* (Future: RETURN, TRANSFER, SHRINK, SCRAP, etc.)

On-hand quantity is computed as:

```
SUM(quantity_delta) WHERE occurred_at <= as_of
```

### Weighted Average Cost (WAC)

* Calculated per product per store
* Influenced **only by RECEIVE events**
* Supports backdating
* Rounded to nearest cent
* Never stored as mutable state

### Locked Sale Cost (COGS Snapshot)

When a SALE occurs:

* WAC is computed **as of the sale’s occurred_at**
* `unit_cost_cents_at_sale` is snapshotted
* `cogs_cents = unit_cost_cents_at_sale * quantity`
* These values are **immutable forever**

Later backdated RECEIVEs may change historical WAC **but never rewrite prior sale COGS**.

This has been explicitly tested and verified.

---

## 6. Master Ledger (Audit Spine)

In addition to domain-specific ledgers (inventory, loyalty, etc.), there is a **Master Ledger**:

* Append-only
* Cross-domain
* Provides a chronological audit spine
* Every meaningful event is recorded:

  * Product lifecycle events
  * Inventory movements
  * Sales
  * (Later: payments, overrides, security events)

The master ledger exists so the system can always answer:

> “What happened, in what order, and why?”

---

## 7. Identifier System (First-Class Concept)

Identifiers are **not just strings on products**. They are first-class records.

Each identifier has:

* **Type**: SKU, UPC, ALT_BARCODE, VENDOR_CODE, etc.
* **Scope**: org, store, vendor
* **Normalization rules**
* **Uniqueness rules**:

  * Global uniqueness for scannable codes (SKU, UPC)
  * Scoped uniqueness for vendor codes
* Deterministic lookup priority
* Hard-stop on ambiguity (conflict UI required)

This prevents silent mis-scans and supplier barcode chaos.

---

## 8. Document Lifecycle Model (Draft → Approved → Posted)

Anything that touches:

* Money
* Inventory
* Accounting

Must follow a lifecycle:

```
Draft → Approved → Posted
```

This:

* Prevents accidental posting
* Enables review
* Enables AI-generated drafts later without risk

Examples:

* Sales
* Purchase orders
* Inventory adjustments
* Transfers
* Returns

---

## 9. Security, Auth, and Accountability (Planned, Locked)

* Unique user accounts (no shared logins)
* Role-based permissions with store scoping
* Threshold-based controls (refunds, discounts, payouts)
* Manager override workflows (PIN or biometric)
* Optional or enforced facial recognition for sensitive actions
* Session management and idle timeouts
* Shift sign-in/out for cashier accountability
* Security event logging

---

## 10. Register & Sales Model (In Progress Direction)

Sales are treated as **documents**, not just inventory decrements.

Planned capabilities:

* Scanner-first UI
* Cart editing
* Suspend/recall
* Quotes/estimates
* Receipts (print/email/SMS)
* Drawer control with logging

Payments, taxes, discounts, and customers are **intentionally excluded until later phases**.

---

## 11. Inventory Operations (Locked Direction)

* Append-only ledger
* Explicit negative inventory policy
* Concurrency control to prevent oversell
* Manual adjustments with reason codes and approvals
* Inventory states (sellable, damaged, in-transit, reserved)
* Cycle counts and full counts with variance posting

---

## 12. Data Retention, Backup, and Reliability

* Immutable accounting data retained long-term
* PII anonymized or purged without breaking financial links
* Automated backups
* Periodic restore verification
* Structured logs
* Metrics and alerting
* Restore drills treated as first-class operations

---

## 13. AI (Explicitly Last, Approval-Gated)

AI is **never authoritative**.

Permitted roles:

* Draft generation (e.g., invoice → receiving draft)
* Forecasting and reorder suggestions
* Anomaly detection
* Natural-language Q&A with citations

All AI actions:

* Require human review
* Are logged in an AI audit ledger
* Never post directly to financial or inventory ledgers

---

## 14. Current State of the Codebase

As of now, the system has:

**Core Features (Implemented):**
* Backend-authoritative architecture
* Product master with lifecycle auditing
* Append-only inventory ledger
* Weighted average cost with backdating
* Locked COGS at sale time
* Oversell prevention
* Idempotent sale handling
* Master ledger integration
* Verified invariants via executable audit scripts

**Phase 1: Document Lifecycle (✅ Complete)**
* DRAFT → APPROVED → POSTED state machine
* Only POSTED transactions affect inventory
* Approval/posting audit trail
* Prevents accidental posting

**Phase 2: Identifier System (✅ Complete)**
* ProductIdentifier model (SKU, UPC, ALT_BARCODE, VENDOR_CODE)
* Deterministic lookup with priority
* Prevents barcode conflicts and silent mis-scans

**Phase 3: Sale Documents (✅ Complete)**
* Sale & SaleLine models
* Document-first approach (not inventory-first)
* Cart → Post workflow
* Enables suspend/recall, quotes/estimates

**Phase 4: User Authentication (✅ Basic Implementation)**
* User, Role, UserRole models
* Default roles: admin, manager, cashier
* Stub password hashing (needs bcrypt for production)
* User attribution foundation

**CLI Tools (✅ Complete)**
* `flask init-system` - Initialize everything
* `flask create-user` - Interactive user creation
* `flask list-users` - List all users
* See SETUP.md for complete CLI reference

**Frontend Testing Interface (✅ Complete)**
* Identifier lookup (barcode scanner simulation)
* Sales interface (mini POS)
* Lifecycle manager (approve/post queue)
* Auth interface (register/login)
* All existing features maintained

The system is **intentionally incomplete**, but structurally correct.
See **SETUP.md** for installation and CLI commands.

---

## 15. How to Work on This Project

* Make one change at a time
* Explain *why* before changing *how*
* Never weaken backend authority
* Never store derived values
* Never rewrite history
* Never let convenience override auditability

If something feels “easy,” it is probably wrong.

---

## 16. Next Steps (Priority Order)

Now that the foundational architecture is in place, here are the recommended next steps in priority order:

### Phase 6: Production-Ready Authentication (HIGH PRIORITY)
* Replace stub password hashing with bcrypt
* Implement proper session management with secure tokens
* Add password strength requirements and validation
* Implement session timeout and idle logout
* Add "remember me" functionality (optional)
* Enable HTTPS enforcement for production

**Why first:** The current auth system uses `STUB_HASH_password` which is explicitly insecure. This must be hardened before any production use.

### Phase 7: Role-Based Permissions (HIGH PRIORITY)
* Define permission constants (e.g., `CAN_APPROVE_ADJUSTMENTS`, `CAN_POST_SALES`, `CAN_MANAGE_USERS`)
* Implement permission checking decorators/middleware
* Assign default permissions to roles (admin, manager, cashier)
* Add store-scoping to user permissions
* Implement manager override workflows (PIN or biometric)
* Add security event logging for permission checks

**Why second:** Roles exist but don't enforce anything yet. This is critical for accountability and preventing unauthorized actions.

### Phase 8: Register Model & Session Management (MEDIUM PRIORITY)
* Create Register model (device_id, location, current_user, current_shift)
* Implement shift sign-in/sign-out with audit trail
* Add cash drawer tracking (opening balance, transactions, closing balance)
* Create RegisterSession model for shift accountability
* Add register assignment to Sale documents
* Implement drawer open/close events with logging

**Why third:** Needed for multi-register stores and cashier accountability. Builds on auth foundation.

### Phase 9: Payment Processing (MEDIUM PRIORITY)
* Create Tender model (CASH, CARD, CHECK, etc.)
* Create Payment model linked to Sales
* Implement split payments and partial payments
* Add change calculation and cash handling
* Create PaymentTransaction ledger (append-only)
* Implement payment reversal workflows
* Add receipt generation (print/email/SMS)

**Why fourth:** Sales currently have no payment mechanism. This makes the system actually usable for real transactions.

### Phase 10: Returns & COGS Reversal (MEDIUM PRIORITY)
* Create Return model (references original Sale)
* Implement return workflows with approval requirements
* Add COGS reversal logic (credit original sale cost, not current WAC)
* Create RETURN transaction type for inventory ledger
* Implement restocking fees (optional)
* Add return authorization and tracking

**Why fifth:** Common retail operation that requires careful COGS handling. Builds on Sale and Payment infrastructure.

### Phase 11: Enhanced Inventory Operations (LOWER PRIORITY)
* Add inventory states (SELLABLE, DAMAGED, IN_TRANSIT, RESERVED)
* Implement transfer workflows between stores
* Add cycle count and full count workflows
* Create variance posting with approval
* Implement lot/serial number tracking (optional)
* Add expiration date tracking (optional)
* Create SHRINK, SCRAP, TRANSFER transaction types

**Why sixth:** Nice-to-have improvements that don't block core retail operations.

### Phase 12: Concurrency Hardening (LOWER PRIORITY)
* Add optimistic locking with version fields
* Implement row-level locking for critical operations
* Add transaction retry logic for deadlocks
* Create stress tests for concurrent sales
* Document concurrency guarantees and limitations

**Why seventh:** Current implementation has basic oversell prevention. This adds enterprise-grade concurrency handling.

### Phase 13: Multi-Store Infrastructure (LOWER PRIORITY)
* Audit all queries for store_id filtering
* Implement cross-store transfers with approval
* Add store-level configuration and settings
* Create store hierarchy model (optional)
* Implement consolidated reporting across stores

**Why eighth:** Most businesses start with one store. Multi-store can wait until proven at single-store scale.

### Phase 14: Reporting & Analytics (LOWER PRIORITY)
* Implement sales reports (daily, weekly, monthly)
* Add inventory valuation reports
* Create COGS and margin analysis
* Implement ABC analysis for inventory
* Add slow-moving and dead stock reports
* Create audit trail queries and reports

**Why ninth:** Critical for business insights but not blocking core operations.

### Phase 15: AI Integration (LAST)
* Implement AI audit ledger (all AI actions logged)
* Create draft generation for receiving (invoice → draft)
* Add reorder point suggestions with human approval
* Implement anomaly detection for inventory and sales
* Add natural-language Q&A with citation requirements
* **Never allow AI to post directly to ledgers**

**Why last:** AI must never be authoritative. All AI actions require human review and approval. Build this only after the system is proven correct and stable.

---

## 17. Known Limitations & Technical Debt

* **Auth security:** Password hashing is stubbed (STUB_HASH_password)
* **Session management:** No token-based sessions or expiration
* **Permissions:** Roles exist but don't enforce anything
* **Concurrency:** Basic oversell prevention only, no optimistic locking
* **Payments:** Not implemented - sales can't be paid
* **Returns:** Not implemented - no reversal mechanism
* **Registers:** No device/shift tracking
* **Multi-store:** Not tested, may have data leakage issues
* **Receipts:** Not implemented
* **Taxes:** Not implemented
* **Discounts:** Not implemented
* **Customers:** Not implemented
* **Loyalty:** Not implemented

**These are intentional.** The system is structurally correct but functionally incomplete. Build incrementally, test thoroughly, never weaken the foundation.

---

**APOS is a system designed to be trusted.
Trust comes from correctness, not speed.**
# APOS
