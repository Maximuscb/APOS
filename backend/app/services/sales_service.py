"""
Phase 3: Sales Service - Document-first sale processing

WHY: Separates sale intent from inventory posting. Enables cart editing,
suspend/recall, and proper lifecycle.
"""

from sqlalchemy import text

from ..extensions import db
from ..models import Sale, SaleLine, Product, InventoryTransaction, Payment
from app.time_utils import utcnow
from .inventory_service import sell_inventory, get_quantity_on_hand
from .document_service import next_document_number
from .ledger_service import append_ledger_event
from .concurrency import lock_for_update, run_with_retry


class SaleError(Exception):
    """Raised for sale operation errors."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


def _validate_on_hand(sale: Sale, lines: list[SaleLine]) -> None:
    product_totals: dict[int, int] = {}
    for line in lines:
        product_totals[line.product_id] = product_totals.get(line.product_id, 0) + line.quantity

    insufficient = []
    for product_id, qty in product_totals.items():
        on_hand = get_quantity_on_hand(sale.store_id, product_id)
        if on_hand < qty:
            insufficient.append({
                "product_id": product_id,
                "requested_quantity": qty,
                "on_hand": on_hand,
            })

    if insufficient:
        raise SaleError(
            "Insufficient inventory to post sale",
            details={"items": insufficient},
        )

def create_sale(store_id: int, user_id: int | None = None) -> Sale:
    """Create new draft sale document."""
    doc_num = next_document_number(store_id=store_id, document_type="SALE", prefix="S")

    sale = Sale(
        store_id=store_id,
        document_number=doc_num,
        status="DRAFT",
        created_by_user_id=user_id
    )

    db.session.add(sale)
    db.session.commit()
    return sale


def add_line(sale_id: int, product_id: int, quantity: int) -> SaleLine:
    """Add line item to draft sale."""
    def _op():
        sale = lock_for_update(db.session.query(Sale).filter_by(id=sale_id)).first()
        if not sale:
            raise SaleError("Sale not found")

        if sale.status != "DRAFT":
            if sale.status == "VOIDED":
                raise SaleError("Cannot add lines to VOIDED sales")
            raise SaleError("Can only add lines to DRAFT sales")

        product = db.session.query(Product).filter_by(id=product_id).first()
        if not product:
            raise SaleError("Product not found")

        if product.price_cents is None:
            raise SaleError("Product has no price")

        line_total = product.price_cents * quantity

        line = SaleLine(
            sale_id=sale_id,
            product_id=product_id,
            quantity=quantity,
            unit_price_cents=product.price_cents,
            line_total_cents=line_total
        )

        db.session.add(line)
        db.session.commit()
        return line

    return run_with_retry(_op)

def _post_sale_locked(sale: Sale, lines: list[SaleLine], actor_user_id: int | None = None) -> Sale:
    if sale.status == "POSTED":
        return sale

    if sale.status != "DRAFT":
        raise SaleError(f"Cannot post sale with status {sale.status}")

    if not lines:
        raise SaleError("Cannot post sale with no lines")

    _validate_on_hand(sale, lines)

    for i, line in enumerate(lines):
        inv_tx = sell_inventory(
            store_id=sale.store_id,
            product_id=line.product_id,
            quantity=line.quantity,
            sale_id=sale.document_number,
            sale_line_id=str(i + 1),
            status="POSTED",
            note=f"Sale {sale.document_number}",
            commit=False,
            posted_by_user_id=actor_user_id or sale.created_by_user_id,
        )
        line.inventory_transaction_id = inv_tx.id

    sale.status = "POSTED"
    sale.completed_at = utcnow()

    append_ledger_event(
        store_id=sale.store_id,
        event_type="sale.posted",
        event_category="sales",
        entity_type="sale",
        entity_id=sale.id,
        actor_user_id=actor_user_id or sale.created_by_user_id,
        register_id=sale.register_id,
        register_session_id=sale.register_session_id,
        sale_id=sale.id,
        occurred_at=sale.completed_at,
        note=f"Sale {sale.document_number} posted",
    )

    return sale


def post_sale(sale_id: int, user_id: int | None = None) -> Sale:
    """
    Post sale - creates inventory transactions with lifecycle=POSTED.
    This is the bridge between sale document and inventory ledger.
    """
    def _op():
        if db.engine.dialect.name == "sqlite":
            db.session.execute(text("BEGIN IMMEDIATE"))
        sale = lock_for_update(db.session.query(Sale).filter_by(id=sale_id)).first()
        if not sale:
            raise SaleError("Sale not found")

        lines = db.session.query(SaleLine).filter_by(sale_id=sale_id).all()
        _post_sale_locked(sale, lines, actor_user_id=user_id or sale.created_by_user_id)

        db.session.commit()
        return sale

    return run_with_retry(_op)


def void_sale(
    sale_id: int,
    user_id: int,
    reason: str,
    register_id: int | None = None,
    register_session_id: int | None = None,
) -> Sale:
    """
    Void a posted sale and reverse its financial and inventory effects.
    """
    from .payment_service import _log_payment_transaction, _update_sale_payment_status

    def _op():
        sale = lock_for_update(db.session.query(Sale).filter_by(id=sale_id)).first()
        if not sale:
            raise SaleError("Sale not found")

        if sale.status == "VOIDED":
            raise SaleError("Sale already voided")

        if sale.status != "POSTED":
            raise SaleError("Only POSTED sales can be voided")

        lines = db.session.query(SaleLine).filter_by(sale_id=sale.id).all()
        if not lines:
            raise SaleError("Cannot void sale with no lines")

        for line in lines:
            if not line.inventory_transaction_id:
                raise SaleError("Sale line missing inventory transaction")

            original_tx = db.session.query(InventoryTransaction).get(line.inventory_transaction_id)
            if not original_tx:
                raise SaleError("Original inventory transaction not found")

            unit_cost_cents = original_tx.unit_cost_cents_at_sale
            cogs_cents = None
            if unit_cost_cents is not None:
                cogs_cents = -unit_cost_cents * line.quantity

            reversal_tx = InventoryTransaction(
                store_id=sale.store_id,
                product_id=line.product_id,
                type="SALE_VOID",
                quantity_delta=line.quantity,
                unit_cost_cents=None,
                note=f"Void sale {sale.document_number}",
                occurred_at=utcnow(),
                status="POSTED",
                sale_id=sale.document_number,
                sale_line_id=f"VOID-{line.id}",
                unit_cost_cents_at_sale=unit_cost_cents,
                cogs_cents=cogs_cents,
                posted_by_user_id=user_id,
                posted_at=utcnow(),
            )

            db.session.add(reversal_tx)
            db.session.flush()

            append_ledger_event(
                store_id=sale.store_id,
                event_type="inventory.sale_voided",
                event_category="inventory",
                entity_type="inventory_transaction",
                entity_id=reversal_tx.id,
                actor_user_id=user_id,
                register_id=register_id or sale.register_id,
                register_session_id=register_session_id or sale.register_session_id,
                sale_id=sale.id,
                occurred_at=reversal_tx.occurred_at,
                note=reversal_tx.note,
                payload=f"product_id={line.product_id},quantity={line.quantity}",
            )

        # Void all completed payments
        payments = db.session.query(Payment).filter_by(sale_id=sale.id, status="COMPLETED").all()
        for payment in payments:
            payment.status = "VOIDED"
            payment.voided_by_user_id = user_id
            payment.voided_at = utcnow()
            payment.void_reason = reason

            _log_payment_transaction(
                payment_id=payment.id,
                sale_id=sale.id,
                transaction_type="VOID",
                amount_cents=-payment.amount_cents,
                tender_type=payment.tender_type,
                user_id=user_id,
                reason=reason,
                register_id=register_id or payment.register_id,
                register_session_id=register_session_id or payment.register_session_id,
            )

            append_ledger_event(
                store_id=sale.store_id,
                event_type="payment.voided",
                event_category="payment",
                entity_type="payment",
                entity_id=payment.id,
                actor_user_id=user_id,
                register_id=register_id or payment.register_id,
                register_session_id=register_session_id or payment.register_session_id,
                sale_id=sale.id,
                payment_id=payment.id,
                occurred_at=payment.voided_at,
                note=reason,
            )

        sale.status = "VOIDED"
        sale.voided_by_user_id = user_id
        sale.voided_at = utcnow()
        sale.void_reason = reason

        append_ledger_event(
            store_id=sale.store_id,
            event_type="sale.voided",
            event_category="sales",
            entity_type="sale",
            entity_id=sale.id,
            actor_user_id=user_id,
            register_id=register_id or sale.register_id,
            register_session_id=register_session_id or sale.register_session_id,
            sale_id=sale.id,
            occurred_at=sale.voided_at,
            note=reason,
        )

        _update_sale_payment_status(sale.id)
        sale.payment_status = "VOIDED"

        db.session.commit()
        return sale

    return run_with_retry(_op)
