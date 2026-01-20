# Overview: Service-layer operations for payment; encapsulates business logic and database work.

"""
Payment Processing Service

WHY: Enable sales to be paid with cash, cards, checks, and other tender types.
Supports split payments, change calculation, and payment voids.

DESIGN PRINCIPLES:
- Payments are separate from sales (many-to-one relationship)
- Split payments: One sale can have multiple payments
- Partial payments: Payment can be less than total due (layaway, deposits)
- Immutable ledger: All payment events logged to payment_transactions
- Change tracking: Cash over-tender calculated automatically
"""

from ..extensions import db
from ..models import Sale, SaleLine, Payment, PaymentTransaction, RegisterSession
from app.time_utils import utcnow
from .concurrency import lock_for_update, run_with_retry
from .ledger_service import append_ledger_event


class PaymentError(Exception):
    """Raised for payment operation errors."""
    pass


# =============================================================================
# TENDER TYPES (CONSTANTS)
# =============================================================================

TENDER_CASH = "CASH"
TENDER_CARD = "CARD"
TENDER_CHECK = "CHECK"
TENDER_GIFT_CARD = "GIFT_CARD"
TENDER_STORE_CREDIT = "STORE_CREDIT"

VALID_TENDER_TYPES = [
    TENDER_CASH,
    TENDER_CARD,
    TENDER_CHECK,
    TENDER_GIFT_CARD,
    TENDER_STORE_CREDIT,
]


# =============================================================================
# PAYMENT STATUS (CONSTANTS)
# =============================================================================

PAYMENT_STATUS_UNPAID = "UNPAID"
PAYMENT_STATUS_PARTIAL = "PARTIAL"
PAYMENT_STATUS_PAID = "PAID"
PAYMENT_STATUS_OVERPAID = "OVERPAID"


# =============================================================================
# PAYMENT CREATION
# =============================================================================

def add_payment(
    sale_id: int,
    user_id: int,
    tender_type: str,
    amount_cents: int,
    reference_number: str | None = None,
    register_id: int | None = None,
    register_session_id: int | None = None
) -> Payment:
    """
    Add a payment to a sale.

    WHY: Core payment operation. Validates payment, calculates change,
    updates sale payment status, and logs to payment ledger.

    Args:
        sale_id: Sale being paid
        user_id: User processing payment
        tender_type: CASH, CARD, CHECK, GIFT_CARD, STORE_CREDIT
        amount_cents: Amount tendered (in cents)
        reference_number: Card auth code, check number, etc. (optional)
        register_id: Register where payment taken (optional)
        register_session_id: Session where payment taken (optional)

    Returns:
        Payment record

    Raises:
        PaymentError: If sale not found, amount invalid, or tender type invalid
    """
    def _op():
        # Validate tender type
        if tender_type not in VALID_TENDER_TYPES:
            raise PaymentError(f"Invalid tender type: {tender_type}. Must be one of {VALID_TENDER_TYPES}")

        # Validate amount
        if amount_cents <= 0:
            raise PaymentError("Payment amount must be positive")

        # Get sale (locked for payment updates)
        sale = lock_for_update(db.session.query(Sale).filter_by(id=sale_id)).first()
        if not sale:
            raise PaymentError(f"Sale {sale_id} not found")

        if sale.status == "VOIDED":
            raise PaymentError("Cannot add payment to a VOIDED sale")

        # Auto-post draft sale inside the same transaction
        if sale.status == "DRAFT":
            from .sales_service import _post_sale_locked, SaleError
            lines = db.session.query(SaleLine).filter_by(sale_id=sale_id).all()
            try:
                _post_sale_locked(sale, lines, actor_user_id=user_id)
            except SaleError as exc:
                raise PaymentError(str(exc))
        elif sale.status != "POSTED":
            raise PaymentError(f"Cannot add payment to sale with status {sale.status}")

        # Calculate sale total from lines
        total_due = calculate_sale_total(sale_id)

        # Calculate change (for cash over-tender)
        remaining_due = total_due - sale.total_paid_cents
        change_cents = 0

        if remaining_due <= 0:
            raise PaymentError("Sale has no remaining balance due")

        if tender_type != TENDER_CASH and amount_cents > remaining_due:
            raise PaymentError("Non-cash tender cannot exceed remaining balance")

        if tender_type == TENDER_CASH and amount_cents > remaining_due:
            change_cents = amount_cents - remaining_due

        # Create payment
        payment = Payment(
            sale_id=sale_id,
            tender_type=tender_type,
            amount_cents=amount_cents,
            status="COMPLETED",
            reference_number=reference_number,
            change_cents=change_cents,
            created_by_user_id=user_id,
            created_at=utcnow(),
            register_id=register_id,
            register_session_id=register_session_id
        )

        db.session.add(payment)
        db.session.flush()  # Get payment ID

        # Log to payment transaction ledger
        _log_payment_transaction(
            payment_id=payment.id,
            sale_id=sale_id,
            transaction_type="PAYMENT",
            amount_cents=amount_cents,
            tender_type=tender_type,
            user_id=user_id,
            reason=None,
            register_id=register_id,
            register_session_id=register_session_id
        )

        _apply_cash_movement(
            register_session_id=register_session_id,
            tender_type=tender_type,
            amount_cents=amount_cents - change_cents,
        )

        # Update sale payment status
        _update_sale_payment_status(sale_id)

        db.session.commit()

        return payment

    return run_with_retry(_op)


def calculate_sale_total(sale_id: int) -> int:
    """
    Calculate total amount due for a sale from its lines.

    WHY: Sale total is derived from lines, not stored directly.
    This prevents data inconsistency.

    Returns:
        Total in cents
    """
    lines = db.session.query(SaleLine).filter_by(sale_id=sale_id).all()
    return sum(line.line_total_cents for line in lines)


def get_sale_payments(sale_id: int, include_voided: bool = False) -> list[Payment]:
    """
    Get all payments for a sale.

    Args:
        sale_id: Sale ID
        include_voided: Include voided payments (default: False)

    Returns:
        List of payments, ordered by creation time
    """
    query = db.session.query(Payment).filter_by(sale_id=sale_id)

    if not include_voided:
        query = query.filter_by(status="COMPLETED")

    return query.order_by(Payment.created_at).all()


def get_sale_remaining_balance(sale_id: int) -> int:
    """
    Calculate remaining balance due on a sale.

    Returns:
        Amount remaining in cents (can be negative if overpaid)
    """
    sale = db.session.query(Sale).get(sale_id)
    if not sale:
        raise PaymentError(f"Sale {sale_id} not found")

    total_due = calculate_sale_total(sale_id)
    return total_due - sale.total_paid_cents


# =============================================================================
# PAYMENT VOIDS
# =============================================================================

def void_payment(
    payment_id: int,
    user_id: int,
    reason: str,
    register_id: int | None = None,
    register_session_id: int | None = None
) -> Payment:
    """
    Void a payment (reversal for mistakes).

    WHY: Cashier mistakes happen. Voiding allows correction without
    deleting audit trail.

    Args:
        payment_id: Payment to void
        user_id: User voiding payment
        reason: Why payment is being voided
        register_id: Register where void performed
        register_session_id: Session where void performed

    Returns:
        Voided payment

    Raises:
        PaymentError: If payment not found or already voided
    """
    def _op():
        payment = lock_for_update(db.session.query(Payment).filter_by(id=payment_id)).first()

        if not payment:
            raise PaymentError(f"Payment {payment_id} not found")

        if payment.status == "VOIDED":
            raise PaymentError(f"Payment {payment_id} already voided")

        # Lock sale for status update
        sale = lock_for_update(db.session.query(Sale).filter_by(id=payment.sale_id)).first()
        if sale and sale.status == "VOIDED":
            raise PaymentError("Cannot void payment on a VOIDED sale")

        # Void payment
        payment.status = "VOIDED"
        payment.voided_by_user_id = user_id
        payment.voided_at = utcnow()
        payment.void_reason = reason

        # Log void to ledger (negative amount)
        _log_payment_transaction(
            payment_id=payment.id,
            sale_id=payment.sale_id,
            transaction_type="VOID",
            amount_cents=-payment.amount_cents,  # Negative for reversal
            tender_type=payment.tender_type,
            user_id=user_id,
            reason=reason,
            register_id=register_id,
            register_session_id=register_session_id
        )

        _apply_cash_movement(
            register_session_id=register_session_id or payment.register_session_id,
            tender_type=payment.tender_type,
            amount_cents=-payment.amount_cents + (payment.change_cents or 0),
        )

        # Update sale payment status
        _update_sale_payment_status(payment.sale_id)

        db.session.commit()

        return payment

    return run_with_retry(_op)


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _log_payment_transaction(
    payment_id: int,
    sale_id: int,
    transaction_type: str,
    amount_cents: int,
    tender_type: str,
    user_id: int,
    reason: str | None = None,
    register_id: int | None = None,
    register_session_id: int | None = None
) -> PaymentTransaction:
    """
    Log payment event to immutable ledger.

    WHY: Audit trail for all payment activity.
    Every payment, void, or refund is logged here.
    """
    transaction = PaymentTransaction(
        payment_id=payment_id,
        sale_id=sale_id,
        transaction_type=transaction_type,
        amount_cents=amount_cents,
        tender_type=tender_type,
        user_id=user_id,
        reason=reason,
        occurred_at=utcnow(),
        register_id=register_id,
        register_session_id=register_session_id
    )

    db.session.add(transaction)
    db.session.flush()

    event_type = {
        "PAYMENT": "payment.created",
        "VOID": "payment.voided",
        "REFUND": "payment.refunded",
    }.get(transaction_type, "payment.event")

    sale = db.session.query(Sale).get(sale_id) if sale_id else None
    if not sale:
        raise PaymentError("Sale not found for payment transaction")
    store_id = sale.store_id

    append_ledger_event(
        store_id=store_id,
        event_type=event_type,
        event_category="payment",
        entity_type="payment_transaction",
        entity_id=transaction.id,
        actor_user_id=user_id,
        register_id=register_id,
        register_session_id=register_session_id,
        sale_id=sale_id,
        payment_id=payment_id,
        occurred_at=transaction.occurred_at,
        note=reason,
        payload=f"tender_type={tender_type},amount_cents={amount_cents}",
    )
    return transaction


def _update_sale_payment_status(sale_id: int) -> None:
    """
    Recalculate and update sale payment status.

    WHY: Payment status (UNPAID, PARTIAL, PAID, OVERPAID) must be
    kept in sync as payments are added or voided.

    PAYMENT STATUS:
    - UNPAID: total_paid = 0
    - PARTIAL: 0 < total_paid < total_due
    - PAID: total_paid = total_due
    - OVERPAID: total_paid > total_due (cash over-tender)
    """
    sale = db.session.query(Sale).get(sale_id)
    if not sale:
        return

    # Calculate total due
    total_due = calculate_sale_total(sale_id)

    # Calculate total paid (sum of completed payments, excluding change)
    payments = get_sale_payments(sale_id, include_voided=False)
    total_paid = sum(p.amount_cents - p.change_cents for p in payments)

    # Apply refunds (negative amounts)
    refund_total = db.session.query(
        db.func.coalesce(db.func.sum(PaymentTransaction.amount_cents), 0)
    ).filter(
        PaymentTransaction.sale_id == sale_id,
        PaymentTransaction.transaction_type == "REFUND",
    ).scalar() or 0

    total_paid += int(refund_total)

    # Calculate change due (sum of all change given)
    change_due = sum(p.change_cents for p in payments)

    # Determine payment status
    if sale.status == "VOIDED":
        payment_status = "VOIDED"
    elif total_paid == 0:
        payment_status = PAYMENT_STATUS_UNPAID
    elif total_paid < total_due:
        payment_status = PAYMENT_STATUS_PARTIAL
    elif total_paid == total_due:
        payment_status = PAYMENT_STATUS_PAID
    else:
        payment_status = PAYMENT_STATUS_OVERPAID

    # Update sale
    sale.total_due_cents = total_due
    sale.total_paid_cents = total_paid
    sale.change_due_cents = change_due
    sale.payment_status = payment_status


def _apply_cash_movement(
    *,
    register_session_id: int | None,
    tender_type: str,
    amount_cents: int,
) -> None:
    if not register_session_id or tender_type != TENDER_CASH:
        return

    session = lock_for_update(db.session.query(RegisterSession).filter_by(id=register_session_id)).first()
    if not session:
        return

    expected_cash = session.expected_cash_cents if session.expected_cash_cents is not None else session.opening_cash_cents
    session.expected_cash_cents = expected_cash + amount_cents


def refund_payment(
    payment_id: int,
    user_id: int,
    amount_cents: int,
    tender_type: str,
    reason: str,
    register_id: int | None = None,
    register_session_id: int | None = None,
) -> PaymentTransaction:
    """
    Refund a payment by logging a negative PaymentTransaction.
    """
    def _op():
        if amount_cents <= 0:
            raise PaymentError("Refund amount must be positive")

        if tender_type not in VALID_TENDER_TYPES:
            raise PaymentError(f"Invalid tender type: {tender_type}. Must be one of {VALID_TENDER_TYPES}")

        payment = lock_for_update(db.session.query(Payment).filter_by(id=payment_id)).first()
        if not payment:
            raise PaymentError(f"Payment {payment_id} not found")

        if payment.status == "VOIDED":
            raise PaymentError("Cannot refund a voided payment")

        if payment.tender_type != tender_type:
            raise PaymentError("Refund tender type must match original payment")

        sale = lock_for_update(db.session.query(Sale).filter_by(id=payment.sale_id)).first()
        if not sale:
            raise PaymentError(f"Sale {payment.sale_id} not found")

        if sale.status == "VOIDED":
            raise PaymentError("Cannot refund a VOIDED sale")

        if sale.total_paid_cents is not None and amount_cents > sale.total_paid_cents:
            raise PaymentError("Refund amount exceeds paid total")

        txn = _log_payment_transaction(
            payment_id=payment.id,
            sale_id=payment.sale_id,
            transaction_type="REFUND",
            amount_cents=-amount_cents,
            tender_type=tender_type,
            user_id=user_id,
            reason=reason,
            register_id=register_id or payment.register_id,
            register_session_id=register_session_id or payment.register_session_id,
        )

        _apply_cash_movement(
            register_session_id=register_session_id or payment.register_session_id,
            tender_type=tender_type,
            amount_cents=-amount_cents,
        )

        _update_sale_payment_status(payment.sale_id)

        db.session.commit()
        return txn

    return run_with_retry(_op)


# =============================================================================
# REPORTING
# =============================================================================

def get_payment_summary(sale_id: int) -> dict:
    """
    Get comprehensive payment summary for a sale.

    Returns:
        - total_due: Amount sale totals to
        - total_paid: Amount paid so far
        - remaining: Amount still owed
        - change_due: Change owed to customer
        - payment_status: UNPAID, PARTIAL, PAID, OVERPAID
        - payments: List of payment records
    """
    sale = db.session.query(Sale).get(sale_id)
    if not sale:
        raise PaymentError(f"Sale {sale_id} not found")

    payments = get_sale_payments(sale_id, include_voided=False)
    remaining = get_sale_remaining_balance(sale_id)

    return {
        "total_due_cents": sale.total_due_cents,
        "total_paid_cents": sale.total_paid_cents,
        "remaining_cents": remaining,
        "change_due_cents": sale.change_due_cents,
        "payment_status": sale.payment_status,
        "payments": [p.to_dict() for p in payments],
    }


def get_payment_transactions(payment_id: int) -> list[PaymentTransaction]:
    """Get all transactions for a payment (payment + voids)."""
    return db.session.query(PaymentTransaction).filter_by(
        payment_id=payment_id
    ).order_by(PaymentTransaction.occurred_at).all()


def get_tender_summary(register_session_id: int) -> dict:
    """
    Get tender summary for a register session.

    WHY: At shift close, cashiers need to know how much of each
    tender type was collected.

    Returns:
        Dictionary with tender type totals:
        {"CASH": 50000, "CARD": 75000, "CHECK": 12500}
    """
    payments = db.session.query(Payment).filter_by(
        register_session_id=register_session_id,
        status="COMPLETED"
    ).all()

    tender_totals = {}
    for payment in payments:
        tender_type = payment.tender_type
        # For cash, subtract change given
        amount = payment.amount_cents - payment.change_cents
        tender_totals[tender_type] = tender_totals.get(tender_type, 0) + amount

    return tender_totals
