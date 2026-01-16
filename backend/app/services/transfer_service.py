# backend/app/services/transfer_service.py
"""
Phase 11: Inter-store transfer service.

WHY: Manage inventory transfers between stores with proper workflow,
approval, and accountability. Creates TRANSFER inventory transactions
at both source and destination stores.

LIFECYCLE:
1. PENDING: Transfer created, lines added
2. APPROVED: Manager approved
3. IN_TRANSIT: Shipped from source (creates negative TRANSFER txn)
4. RECEIVED: Received at destination (creates positive TRANSFER txn)
5. CANCELLED: Cancelled before shipping
"""
from __future__ import annotations
from app.extensions import db
from app.models import Transfer, TransferLine, InventoryTransaction, Product
from app.services.inventory_service import get_quantity_on_hand, get_weighted_average_cost_cents
from app.services.concurrency import lock_for_update, run_with_retry
from app.services.document_service import next_document_number
from app.services.ledger_service import append_ledger_event
from typing import Optional
from datetime import datetime, timezone


# Transfer status constants
TRANSFER_STATUS_PENDING = "PENDING"
TRANSFER_STATUS_APPROVED = "APPROVED"
TRANSFER_STATUS_IN_TRANSIT = "IN_TRANSIT"
TRANSFER_STATUS_RECEIVED = "RECEIVED"
TRANSFER_STATUS_CANCELLED = "CANCELLED"


class TransferError(Exception):
    """Raised when transfer operations fail."""
    pass


def create_transfer(
    from_store_id: int,
    to_store_id: int,
    user_id: int,
    reason: str | None = None
) -> Transfer:
    """
    Create a new transfer document (status: PENDING).

    Args:
        from_store_id: Source store ID
        to_store_id: Destination store ID
        user_id: User creating the transfer
        reason: Optional reason for transfer

    Returns:
        Transfer: The created transfer document

    Raises:
        TransferError: If validation fails
    """
    def _op():
        if from_store_id == to_store_id:
            raise TransferError("Cannot transfer to the same store")

        document_number = next_document_number(
            store_id=from_store_id,
            document_type="TRANSFER",
            prefix="T",
        )

        transfer = Transfer(
            from_store_id=from_store_id,
            to_store_id=to_store_id,
            document_number=document_number,
            status=TRANSFER_STATUS_PENDING,
            reason=reason,
            created_by_user_id=user_id,
        )

        db.session.add(transfer)
        db.session.flush()  # Get ID

        append_ledger_event(
            store_id=from_store_id,
            event_type="transfer.created",
            event_category="transfers",
            entity_type="transfer",
            entity_id=transfer.id,
            actor_user_id=user_id,
            transfer_id=transfer.id,
            occurred_at=transfer.created_at,
            note=reason,
        )

        return transfer

    return run_with_retry(_op)


def add_transfer_line(
    transfer_id: int,
    product_id: int,
    quantity: int
) -> TransferLine:
    """
    Add a line item to a transfer.

    Args:
        transfer_id: Transfer document ID
        product_id: Product to transfer
        quantity: Quantity to transfer

    Returns:
        TransferLine: The created transfer line

    Raises:
        TransferError: If validation fails
    """
    def _op():
        transfer = lock_for_update(db.session.query(Transfer).filter_by(id=transfer_id)).first()
        if not transfer:
            raise TransferError(f"Transfer {transfer_id} not found")

        if transfer.status != TRANSFER_STATUS_PENDING:
            raise TransferError(f"Cannot add lines to transfer in {transfer.status} status")

        if quantity <= 0:
            raise TransferError("Quantity must be positive")

        # Verify product exists (lock to prevent concurrent depletion)
        product = lock_for_update(db.session.query(Product).filter_by(id=product_id)).first()
        if not product:
            raise TransferError(f"Product {product_id} not found")

        # Verify sufficient inventory at source store
        on_hand = get_quantity_on_hand(transfer.from_store_id, product_id)
        if on_hand < quantity:
            raise TransferError(
                f"Insufficient inventory for product {product_id}. "
                f"On-hand: {on_hand}, requested: {quantity}"
            )

        # Check if product already on this transfer
        existing = db.session.query(TransferLine).filter_by(
            transfer_id=transfer_id,
            product_id=product_id
        ).first()

        if existing:
            raise TransferError(f"Product {product_id} already on this transfer")

        line = TransferLine(
            transfer_id=transfer_id,
            product_id=product_id,
            quantity=quantity,
        )

        db.session.add(line)
        db.session.flush()

        return line

    return run_with_retry(_op)


def approve_transfer(
    transfer_id: int,
    user_id: int
) -> Transfer:
    """
    Approve a transfer (manager action).

    Args:
        transfer_id: Transfer document ID
        user_id: User approving the transfer

    Returns:
        Transfer: The approved transfer

    Raises:
        TransferError: If validation fails
    """
    def _op():
        transfer = lock_for_update(db.session.query(Transfer).filter_by(id=transfer_id)).first()
        if not transfer:
            raise TransferError(f"Transfer {transfer_id} not found")

        if transfer.status != TRANSFER_STATUS_PENDING:
            raise TransferError(f"Cannot approve transfer in {transfer.status} status")

        if not transfer.lines:
            raise TransferError("Cannot approve transfer with no lines")

        transfer.status = TRANSFER_STATUS_APPROVED
        transfer.approved_by_user_id = user_id
        transfer.approved_at = datetime.now(timezone.utc)

        append_ledger_event(
            store_id=transfer.from_store_id,
            event_type="transfer.approved",
            event_category="transfers",
            entity_type="transfer",
            entity_id=transfer.id,
            actor_user_id=user_id,
            transfer_id=transfer.id,
            occurred_at=transfer.approved_at,
        )

        return transfer

    return run_with_retry(_op)


def ship_transfer(
    transfer_id: int,
    user_id: int
) -> Transfer:
    """
    Ship a transfer (mark as IN_TRANSIT).
    Creates negative TRANSFER transactions at source store.

    Args:
        transfer_id: Transfer document ID
        user_id: User shipping the transfer

    Returns:
        Transfer: The shipped transfer

    Raises:
        TransferError: If validation fails
    """
    def _op():
        transfer = lock_for_update(db.session.query(Transfer).filter_by(id=transfer_id)).first()
        if not transfer:
            raise TransferError(f"Transfer {transfer_id} not found")

        if transfer.status != TRANSFER_STATUS_APPROVED:
            raise TransferError(f"Cannot ship transfer in {transfer.status} status")

        # Create OUT transactions at source store for each line
        for line in transfer.lines:
            # Re-verify sufficient inventory
            on_hand = get_quantity_on_hand(transfer.from_store_id, line.product_id)
            if on_hand < line.quantity:
                raise TransferError(
                    f"Insufficient inventory for product {line.product_id}. "
                    f"On-hand: {on_hand}, required: {line.quantity}"
                )

            unit_cost_cents = get_weighted_average_cost_cents(transfer.from_store_id, line.product_id)
            if unit_cost_cents is None:
                raise TransferError(f"Cannot transfer product {line.product_id} without cost basis")

            line.unit_cost_cents = unit_cost_cents

            # Create negative TRANSFER transaction with IN_TRANSIT state
            out_txn = InventoryTransaction(
                store_id=transfer.from_store_id,
                product_id=line.product_id,
                type="TRANSFER",
                quantity_delta=-line.quantity,  # Negative: leaving store
                unit_cost_cents=unit_cost_cents,
                status="POSTED",  # Immediately affects inventory
                inventory_state="IN_TRANSIT",  # In transit to destination
                posted_by_user_id=user_id,
                posted_at=datetime.now(timezone.utc),
                note=f"Transfer {transfer.document_number} to store {transfer.to_store_id}",
            )

            db.session.add(out_txn)
            db.session.flush()

            # Link transaction to line
            line.out_transaction_id = out_txn.id

            append_ledger_event(
                store_id=transfer.from_store_id,
                event_type="inventory.transfer_out",
                event_category="inventory",
                entity_type="inventory_transaction",
                entity_id=out_txn.id,
                actor_user_id=user_id,
                transfer_id=transfer.id,
                occurred_at=out_txn.posted_at,
                note=out_txn.note,
                payload=f"product_id={line.product_id},quantity={line.quantity},unit_cost_cents={unit_cost_cents}",
            )

        transfer.status = TRANSFER_STATUS_IN_TRANSIT
        transfer.shipped_by_user_id = user_id
        transfer.shipped_at = datetime.now(timezone.utc)

        append_ledger_event(
            store_id=transfer.from_store_id,
            event_type="transfer.shipped",
            event_category="transfers",
            entity_type="transfer",
            entity_id=transfer.id,
            actor_user_id=user_id,
            transfer_id=transfer.id,
            occurred_at=transfer.shipped_at,
        )

        return transfer

    return run_with_retry(_op)


def receive_transfer(
    transfer_id: int,
    user_id: int
) -> Transfer:
    """
    Receive a transfer at destination store.
    Creates positive TRANSFER transactions at destination.

    Args:
        transfer_id: Transfer document ID
        user_id: User receiving the transfer

    Returns:
        Transfer: The received transfer

    Raises:
        TransferError: If validation fails
    """
    def _op():
        transfer = lock_for_update(db.session.query(Transfer).filter_by(id=transfer_id)).first()
        if not transfer:
            raise TransferError(f"Transfer {transfer_id} not found")

        if transfer.status != TRANSFER_STATUS_IN_TRANSIT:
            raise TransferError(f"Cannot receive transfer in {transfer.status} status")

        # Create IN transactions at destination store for each line
        for line in transfer.lines:
            unit_cost_cents = line.unit_cost_cents
            if unit_cost_cents is None:
                raise TransferError("Transfer line missing unit cost")

            # Create positive TRANSFER transaction with SELLABLE state
            in_txn = InventoryTransaction(
                store_id=transfer.to_store_id,
                product_id=line.product_id,
                type="TRANSFER",
                quantity_delta=line.quantity,  # Positive: arriving at store
                unit_cost_cents=unit_cost_cents,
                status="POSTED",  # Immediately affects inventory
                inventory_state="SELLABLE",  # Ready for sale
                posted_by_user_id=user_id,
                posted_at=datetime.now(timezone.utc),
                note=f"Transfer {transfer.document_number} from store {transfer.from_store_id}",
            )

            db.session.add(in_txn)
            db.session.flush()

            # Link transaction to line
            line.in_transaction_id = in_txn.id

            append_ledger_event(
                store_id=transfer.to_store_id,
                event_type="inventory.transfer_in",
                event_category="inventory",
                entity_type="inventory_transaction",
                entity_id=in_txn.id,
                actor_user_id=user_id,
                transfer_id=transfer.id,
                occurred_at=in_txn.posted_at,
                note=in_txn.note,
                payload=f"product_id={line.product_id},quantity={line.quantity},unit_cost_cents={unit_cost_cents}",
            )

        transfer.status = TRANSFER_STATUS_RECEIVED
        transfer.received_by_user_id = user_id
        transfer.received_at = datetime.now(timezone.utc)

        append_ledger_event(
            store_id=transfer.to_store_id,
            event_type="transfer.received",
            event_category="transfers",
            entity_type="transfer",
            entity_id=transfer.id,
            actor_user_id=user_id,
            transfer_id=transfer.id,
            occurred_at=transfer.received_at,
        )

        return transfer

    return run_with_retry(_op)


def cancel_transfer(
    transfer_id: int,
    user_id: int,
    reason: str
) -> Transfer:
    """
    Cancel a transfer before shipping.

    Args:
        transfer_id: Transfer document ID
        user_id: User cancelling the transfer
        reason: Reason for cancellation

    Returns:
        Transfer: The cancelled transfer

    Raises:
        TransferError: If validation fails
    """
    def _op():
        transfer = lock_for_update(db.session.query(Transfer).filter_by(id=transfer_id)).first()
        if not transfer:
            raise TransferError(f"Transfer {transfer_id} not found")

        if transfer.status not in [TRANSFER_STATUS_PENDING, TRANSFER_STATUS_APPROVED]:
            raise TransferError(
                f"Cannot cancel transfer in {transfer.status} status. "
                f"Transfers can only be cancelled before shipping."
            )

        transfer.status = TRANSFER_STATUS_CANCELLED
        transfer.cancelled_by_user_id = user_id
        transfer.cancelled_at = datetime.now(timezone.utc)
        transfer.cancellation_reason = reason

        append_ledger_event(
            store_id=transfer.from_store_id,
            event_type="transfer.cancelled",
            event_category="transfers",
            entity_type="transfer",
            entity_id=transfer.id,
            actor_user_id=user_id,
            transfer_id=transfer.id,
            occurred_at=transfer.cancelled_at,
            note=reason,
        )

        return transfer

    return run_with_retry(_op)


def get_transfer_summary(transfer_id: int) -> dict:
    """
    Get transfer summary with lines.

    Args:
        transfer_id: Transfer document ID

    Returns:
        dict: Transfer summary with lines

    Raises:
        TransferError: If transfer not found
    """
    transfer = db.session.query(Transfer).get(transfer_id)
    if not transfer:
        raise TransferError(f"Transfer {transfer_id} not found")

    return {
        **transfer.to_dict(),
        "lines": [line.to_dict() for line in transfer.lines],
    }
