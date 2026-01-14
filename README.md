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

* Backend-authoritative architecture
* Product master with lifecycle auditing
* Append-only inventory ledger
* Weighted average cost with backdating
* Locked COGS at sale time
* Oversell prevention
* Idempotent sale handling
* Master ledger integration
* Verified invariants via executable audit scripts

The system is **intentionally incomplete**, but structurally correct.

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

## 16. Next Directions (When Ready)

* Harden concurrency controls
* Build register-level sale documents
* Introduce tenders/payments
* Add returns with COGS reversal
* Expand inventory operations
* Add users, permissions, and security
* Move toward multi-store
* Only then consider AI

---

**APOS is a system designed to be trusted.
Trust comes from correctness, not speed.**
