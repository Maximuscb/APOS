# Overview: Flask API routes for payments operations; parses input and returns JSON responses.

# backend/app/routes/payments.py
"""
Payment Processing API Routes

WHY: Enable sales to be paid via REST API.
Supports cash, card, check, and other tender types.

DESIGN:
- Add payments to sales (supports split payments)
- Calculate change automatically for cash
- Void payments for mistake correction
- Get payment summary and remaining balance
- Permission-based access control

SECURITY:
- CREATE_SALE permission required for adding payments
- VOID_SALE permission required for voiding payments
- All operations logged to payment_transactions ledger
"""

from flask import Blueprint, request, jsonify, g, current_app
from sqlalchemy import desc

from ..models import Payment, PaymentTransaction, Sale
from ..extensions import db
from ..services import payment_service
from ..services.payment_service import PaymentError
from ..decorators import require_auth, require_permission


payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


# =============================================================================
# PAYMENT CREATION
# =============================================================================

@payments_bp.post("/")
@require_auth
@require_permission("CREATE_SALE")
def add_payment_route():
    """
    Add a payment to a sale.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier

    Request body:
    {
        "sale_id": 123,
        "tender_type": "CASH",
        "amount_cents": 10000,
        "reference_number": "AUTH-12345",  (optional, for cards/checks)
        "register_id": 1,  (optional)
        "register_session_id": 5  (optional)
    }

    TENDER TYPES:
    - CASH: Physical currency (change calculated automatically)
    - CARD: Credit/debit card
    - CHECK: Paper check
    - GIFT_CARD: Store gift card
    - STORE_CREDIT: Store credit/account

    Returns:
        201: Payment created with change calculation
        400: Invalid input
        403: Permission denied
        500: Server error
    """
    try:
        data = request.get_json()

        sale_id = data.get("sale_id")
        tender_type = data.get("tender_type")
        amount_cents = data.get("amount_cents")
        reference_number = data.get("reference_number")
        register_id = data.get("register_id")
        register_session_id = data.get("register_session_id")

        if not all([sale_id, tender_type, amount_cents]):
            return jsonify({"error": "sale_id, tender_type, and amount_cents required"}), 400

        payment = payment_service.add_payment(
            sale_id=sale_id,
            user_id=g.current_user.id,
            tender_type=tender_type,
            amount_cents=amount_cents,
            reference_number=reference_number,
            register_id=register_id,
            register_session_id=register_session_id
        )

        # Get updated sale payment summary
        summary = payment_service.get_payment_summary(sale_id)

        return jsonify({
            "payment": payment.to_dict(),
            "summary": summary
        }), 201

    except PaymentError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to add payment")
        return jsonify({"error": "Internal server error"}), 500


# =============================================================================
# PAYMENT QUERIES
# =============================================================================

@payments_bp.get("/sales/<int:sale_id>")
@require_auth
@require_permission("CREATE_SALE")
def get_sale_payments_route(sale_id: int):
    """
    Get all payments for a sale.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier

    Query params:
    - include_voided: Include voided payments (default: false)

    Returns payment summary including:
    - Total due
    - Total paid
    - Remaining balance
    - Payment status
    - List of payments
    """
    try:
        include_voided = request.args.get("include_voided", "false").lower() == "true"

        # Get sale
        sale = db.session.query(Sale).get(sale_id)
        if not sale:
            return jsonify({"error": "Sale not found"}), 404

        # Get payments
        payments = payment_service.get_sale_payments(sale_id, include_voided=include_voided)

        # Get summary
        summary = payment_service.get_payment_summary(sale_id)

        return jsonify({
            "sale_id": sale_id,
            "payments": [p.to_dict() for p in payments],
            "summary": summary
        }), 200

    except PaymentError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to load sale payments")
        return jsonify({"error": "Internal server error"}), 500


@payments_bp.get("/<int:payment_id>")
@require_auth
@require_permission("CREATE_SALE")
def get_payment_route(payment_id: int):
    """
    Get payment details including all transactions.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier

    Returns payment with full transaction history (payment, voids, refunds).
    """
    payment = db.session.query(Payment).get(payment_id)

    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    # Get transaction history
    transactions = payment_service.get_payment_transactions(payment_id)

    return jsonify({
        "payment": payment.to_dict(),
        "transactions": [t.to_dict() for t in transactions]
    }), 200


@payments_bp.get("/sales/<int:sale_id>/summary")
@require_auth
@require_permission("CREATE_SALE")
def get_payment_summary_route(sale_id: int):
    """
    Get payment summary for a sale.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier

    Returns:
    - total_due_cents: Total from sale lines
    - total_paid_cents: Sum of payments
    - remaining_cents: Amount still owed
    - change_due_cents: Change owed to customer
    - payment_status: UNPAID, PARTIAL, PAID, OVERPAID
    """
    try:
        summary = payment_service.get_payment_summary(sale_id)
        return jsonify(summary), 200

    except PaymentError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to load payment summary")
        return jsonify({"error": "Internal server error"}), 500


# =============================================================================
# PAYMENT VOIDS
# =============================================================================

@payments_bp.post("/<int:payment_id>/void")
@require_auth
@require_permission("VOID_SALE")
def void_payment_route(payment_id: int):
    """
    Void a payment (reversal for mistakes).

    Requires: VOID_SALE permission
    Available to: admin, manager

    Request body:
    {
        "reason": "Customer paid wrong amount",
        "register_id": 1,  (optional)
        "register_session_id": 5  (optional)
    }

    Returns voided payment. Original payment preserved for audit trail.
    """
    try:
        data = request.get_json()
        reason = data.get("reason")
        register_id = data.get("register_id")
        register_session_id = data.get("register_session_id")

        if not reason:
            return jsonify({"error": "reason required"}), 400

        payment = payment_service.void_payment(
            payment_id=payment_id,
            user_id=g.current_user.id,
            reason=reason,
            register_id=register_id,
            register_session_id=register_session_id
        )

        # Get updated sale summary
        summary = payment_service.get_payment_summary(payment.sale_id)

        return jsonify({
            "payment": payment.to_dict(),
            "summary": summary
        }), 200

    except PaymentError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to void payment")
        return jsonify({"error": "Internal server error"}), 500


@payments_bp.post("/<int:payment_id>/refund")
@require_auth
@require_permission("REFUND_PAYMENT")
def refund_payment_route(payment_id: int):
    """
    Refund a payment (negative payment transaction).

    Requires: REFUND_PAYMENT permission
    Available to: admin, manager
    """
    try:
        data = request.get_json()
        reason = data.get("reason")
        amount_cents = data.get("amount_cents")
        tender_type = data.get("tender_type")
        register_id = data.get("register_id")
        register_session_id = data.get("register_session_id")

        if not all([reason, amount_cents, tender_type]):
            return jsonify({"error": "reason, amount_cents, and tender_type required"}), 400

        txn = payment_service.refund_payment(
            payment_id=payment_id,
            user_id=g.current_user.id,
            amount_cents=amount_cents,
            tender_type=tender_type,
            reason=reason,
            register_id=register_id,
            register_session_id=register_session_id,
        )

        summary = payment_service.get_payment_summary(txn.sale_id)

        return jsonify({
            "transaction": txn.to_dict(),
            "summary": summary
        }), 201

    except PaymentError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("Failed to refund payment")
        return jsonify({"error": "Internal server error"}), 500


# =============================================================================
# TENDER REPORTING
# =============================================================================

@payments_bp.get("/sessions/<int:session_id>/tender-summary")
@require_auth
@require_permission("CREATE_SALE")
def get_tender_summary_route(session_id: int):
    """
    Get tender type summary for a register session.

    Requires: CREATE_SALE permission
    Available to: admin, manager, cashier

    Returns breakdown by tender type:
    {
        "CASH": 50000,
        "CARD": 75000,
        "CHECK": 12500
    }

    WHY: At shift close, cashiers need to know how much of each
    tender type was collected for reconciliation.
    """
    try:
        tender_totals = payment_service.get_tender_summary(session_id)

        return jsonify({
            "register_session_id": session_id,
            "tender_totals_cents": tender_totals
        }), 200

    except Exception:
        current_app.logger.exception("Failed to get tender summary")
        return jsonify({"error": "Internal server error"}), 500


# =============================================================================
# TRANSACTION AUDIT TRAIL
# =============================================================================

@payments_bp.get("/transactions")
@require_auth
@require_permission("VIEW_AUDIT_LOG")
def list_payment_transactions_route():
    """
    List payment transactions with filters.

    Requires: VIEW_AUDIT_LOG permission
    Available to: admin, manager

    Query params:
    - sale_id: Filter by sale
    - transaction_type: Filter by type (PAYMENT, VOID, REFUND)
    - start_date: Filter after date (ISO 8601)
    - end_date: Filter before date (ISO 8601)
    - limit: Max transactions (default: 100)

    Returns immutable payment transaction ledger.
    """
    from datetime import datetime
    from sqlalchemy.exc import OperationalError, ProgrammingError

    sale_id = request.args.get("sale_id", type=int)
    transaction_type = request.args.get("transaction_type")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    limit = request.args.get("limit", 100, type=int)

    try:
        query = db.session.query(PaymentTransaction)

        if sale_id:
            query = query.filter_by(sale_id=sale_id)

        if transaction_type:
            query = query.filter_by(transaction_type=transaction_type)

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                query = query.filter(PaymentTransaction.occurred_at >= start_dt)
            except ValueError:
                return jsonify({"error": "Invalid start_date format"}), 400

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                query = query.filter(PaymentTransaction.occurred_at <= end_dt)
            except ValueError:
                return jsonify({"error": "Invalid end_date format"}), 400

        transactions = query.order_by(desc(PaymentTransaction.occurred_at)).limit(limit).all()

        return jsonify({"transactions": [t.to_dict() for t in transactions]}), 200

    except (OperationalError, ProgrammingError) as e:
        # Dev/stress-test friendly behavior:
        # If DB was recreated and migrations haven't run yet, the ledger table may not exist.
        # Return empty list (stable contract) instead of 500.
        msg = str(e).lower()
        if "no such table" in msg or "does not exist" in msg:
            return jsonify({
                "transactions": [],
                "warning": "payment_transactions ledger table is missing; run migrations to enable audit trail"
            }), 200
        current_app.logger.exception("Payment transaction list failed")
        return jsonify({"error": "Database error"}), 500
