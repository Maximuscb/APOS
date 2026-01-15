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
from app.services.inventory_service import get_quantity_on_hand
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
    if from_store_id == to_store_id:
        raise TransferError("Cannot transfer to the same store")

    # Generate document number
    count = db.session.query(Transfer).count()
    document_number = f"T-{str(count + 1).zfill(6)}"

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

    return transfer


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
    transfer = db.session.query(Transfer).get(transfer_id)
    if not transfer:
        raise TransferError(f"Transfer {transfer_id} not found")

    if transfer.status != TRANSFER_STATUS_PENDING:
        raise TransferError(f"Cannot add lines to transfer in {transfer.status} status")

    if quantity <= 0:
        raise TransferError("Quantity must be positive")

    # Verify product exists
    product = db.session.query(Product).get(product_id)
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
    transfer = db.session.query(Transfer).get(transfer_id)
    if not transfer:
        raise TransferError(f"Transfer {transfer_id} not found")

    if transfer.status != TRANSFER_STATUS_PENDING:
        raise TransferError(f"Cannot approve transfer in {transfer.status} status")

    if not transfer.lines:
        raise TransferError("Cannot approve transfer with no lines")

    transfer.status = TRANSFER_STATUS_APPROVED
    transfer.approved_by_user_id = user_id
    transfer.approved_at = datetime.now(timezone.utc)

    return transfer


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
    transfer = db.session.query(Transfer).get(transfer_id)
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

        # Create negative TRANSFER transaction with IN_TRANSIT state
        out_txn = InventoryTransaction(
            store_id=transfer.from_store_id,
            product_id=line.product_id,
            type="TRANSFER",
            quantity_delta=-line.quantity,  # Negative: leaving store
            unit_cost_cents=None,  # Not a RECEIVE
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

    transfer.status = TRANSFER_STATUS_IN_TRANSIT
    transfer.shipped_by_user_id = user_id
    transfer.shipped_at = datetime.now(timezone.utc)

    return transfer


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
    transfer = db.session.query(Transfer).get(transfer_id)
    if not transfer:
        raise TransferError(f"Transfer {transfer_id} not found")

    if transfer.status != TRANSFER_STATUS_IN_TRANSIT:
        raise TransferError(f"Cannot receive transfer in {transfer.status} status")

    # Create IN transactions at destination store for each line
    for line in transfer.lines:
        # Create positive TRANSFER transaction with SELLABLE state
        in_txn = InventoryTransaction(
            store_id=transfer.to_store_id,
            product_id=line.product_id,
            type="TRANSFER",
            quantity_delta=line.quantity,  # Positive: arriving at store
            unit_cost_cents=None,  # Not a RECEIVE
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

    transfer.status = TRANSFER_STATUS_RECEIVED
    transfer.received_by_user_id = user_id
    transfer.received_at = datetime.now(timezone.utc)

    return transfer


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
    transfer = db.session.query(Transfer).get(transfer_id)
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

    return transfer


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
