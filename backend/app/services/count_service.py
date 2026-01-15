# backend/app/services/count_service.py
"""
Phase 11: Physical inventory count service.

WHY: Regular physical counts ensure inventory accuracy. Compares
expected (system) vs. actual (physical) quantities and posts variances
as ADJUST transactions after manager approval.

LIFECYCLE:
1. PENDING: Count created, lines being entered
2. APPROVED: Manager approved, ready to post
3. POSTED: Variances posted to inventory ledger
4. CANCELLED: Cancelled before posting
"""
from __future__ import annotations
from app.extensions import db
from app.models import Count, CountLine, InventoryTransaction
from app.services.inventory_service import get_quantity_on_hand, get_weighted_average_cost_cents
from app.services.concurrency import lock_for_update, run_with_retry
from datetime import datetime, timezone


# Count status constants
COUNT_STATUS_PENDING = "PENDING"
COUNT_STATUS_APPROVED = "APPROVED"
COUNT_STATUS_POSTED = "POSTED"
COUNT_STATUS_CANCELLED = "CANCELLED"

# Count type constants
COUNT_TYPE_CYCLE = "CYCLE"
COUNT_TYPE_FULL = "FULL"


class CountError(Exception):
    """Raised when count operations fail."""
    pass


def create_count(
    store_id: int,
    count_type: str,
    user_id: int,
    reason: str | None = None
) -> Count:
    """
    Create a new count document (status: PENDING).

    Args:
        store_id: Store where count is performed
        count_type: "CYCLE" or "FULL"
        user_id: User creating the count
        reason: Optional reason for count

    Returns:
        Count: The created count document

    Raises:
        CountError: If validation fails
    """
    def _op():
        if count_type not in [COUNT_TYPE_CYCLE, COUNT_TYPE_FULL]:
            raise CountError(f"Invalid count type: {count_type}")

        # Generate document number
        count_num = db.session.query(Count).filter_by(store_id=store_id).count()
        document_number = f"C-{str(count_num + 1).zfill(6)}"

        count = Count(
            store_id=store_id,
            document_number=document_number,
            count_type=count_type,
            status=COUNT_STATUS_PENDING,
            reason=reason,
            created_by_user_id=user_id,
        )

        db.session.add(count)
        db.session.flush()  # Get ID

        return count

    return run_with_retry(_op)


def add_count_line(
    count_id: int,
    product_id: int,
    actual_quantity: int
) -> CountLine:
    """
    Add a line item to a count.
    Automatically fetches expected quantity from system and calculates variance.

    Args:
        count_id: Count document ID
        product_id: Product being counted
        actual_quantity: Physical count quantity

    Returns:
        CountLine: The created count line

    Raises:
        CountError: If validation fails
    """
    def _op():
        count = lock_for_update(db.session.query(Count).filter_by(id=count_id)).first()
        if not count:
            raise CountError(f"Count {count_id} not found")

        if count.status != COUNT_STATUS_PENDING:
            raise CountError(f"Cannot add lines to count in {count.status} status")

        if actual_quantity < 0:
            raise CountError("Actual quantity cannot be negative")

        # Check if product already on this count
        existing = db.session.query(CountLine).filter_by(
            count_id=count_id,
            product_id=product_id
        ).first()

        if existing:
            raise CountError(f"Product {product_id} already on this count")

        # Get expected quantity from system
        expected_quantity = get_quantity_on_hand(count.store_id, product_id)

        # Calculate variance (actual - expected)
        variance_quantity = actual_quantity - expected_quantity

        # Get WAC for cost calculation
        unit_cost_cents = get_weighted_average_cost_cents(count.store_id, product_id)
        variance_cost_cents = variance_quantity * unit_cost_cents if unit_cost_cents else None

        line = CountLine(
            count_id=count_id,
            product_id=product_id,
            expected_quantity=expected_quantity,
            actual_quantity=actual_quantity,
            variance_quantity=variance_quantity,
            unit_cost_cents=unit_cost_cents,
            variance_cost_cents=variance_cost_cents,
        )

        db.session.add(line)
        db.session.flush()

        return line

    return run_with_retry(_op)


def approve_count(
    count_id: int,
    user_id: int
) -> Count:
    """
    Approve a count (manager action).

    Args:
        count_id: Count document ID
        user_id: User approving the count

    Returns:
        Count: The approved count

    Raises:
        CountError: If validation fails
    """
    def _op():
        count = lock_for_update(db.session.query(Count).filter_by(id=count_id)).first()
        if not count:
            raise CountError(f"Count {count_id} not found")

        if count.status != COUNT_STATUS_PENDING:
            raise CountError(f"Cannot approve count in {count.status} status")

        if not count.lines:
            raise CountError("Cannot approve count with no lines")

        # Calculate totals
        total_variance_units = sum(line.variance_quantity for line in count.lines)
        total_variance_cost_cents = sum(
            line.variance_cost_cents for line in count.lines if line.variance_cost_cents
        )

        count.total_variance_units = total_variance_units
        count.total_variance_cost_cents = total_variance_cost_cents
        count.status = COUNT_STATUS_APPROVED
        count.approved_by_user_id = user_id
        count.approved_at = datetime.now(timezone.utc)

        return count

    return run_with_retry(_op)


def post_count(
    count_id: int,
    user_id: int
) -> Count:
    """
    Post a count: create ADJUST transactions for all variances.

    Args:
        count_id: Count document ID
        user_id: User posting the count

    Returns:
        Count: The posted count

    Raises:
        CountError: If validation fails
    """
    def _op():
        count = lock_for_update(db.session.query(Count).filter_by(id=count_id)).first()
        if not count:
            raise CountError(f"Count {count_id} not found")

        if count.status != COUNT_STATUS_APPROVED:
            raise CountError(f"Cannot post count in {count.status} status")

        # Create ADJUST transaction for each line with variance
        for line in count.lines:
            if line.variance_quantity == 0:
                # No variance, skip
                continue

            # Create ADJUST transaction
            txn = InventoryTransaction(
                store_id=count.store_id,
                product_id=line.product_id,
                type="ADJUST",
                quantity_delta=line.variance_quantity,  # Positive or negative
                unit_cost_cents=None,  # Not a RECEIVE
                status="POSTED",  # Immediately affects inventory
                inventory_state="SELLABLE",  # Adjusting sellable inventory
                posted_by_user_id=user_id,
                posted_at=datetime.now(timezone.utc),
                note=f"Count {count.document_number} variance: {line.variance_quantity}",
            )

            db.session.add(txn)
            db.session.flush()

            # Link transaction to line
            line.inventory_transaction_id = txn.id

        count.status = COUNT_STATUS_POSTED
        count.posted_by_user_id = user_id
        count.posted_at = datetime.now(timezone.utc)

        return count

    return run_with_retry(_op)


def cancel_count(
    count_id: int,
    user_id: int,
    reason: str
) -> Count:
    """
    Cancel a count before posting.

    Args:
        count_id: Count document ID
        user_id: User cancelling the count
        reason: Reason for cancellation

    Returns:
        Count: The cancelled count

    Raises:
        CountError: If validation fails
    """
    def _op():
        count = lock_for_update(db.session.query(Count).filter_by(id=count_id)).first()
        if not count:
            raise CountError(f"Count {count_id} not found")

        if count.status not in [COUNT_STATUS_PENDING, COUNT_STATUS_APPROVED]:
            raise CountError(
                f"Cannot cancel count in {count.status} status. "
                f"Counts can only be cancelled before posting."
            )

        count.status = COUNT_STATUS_CANCELLED
        count.cancelled_by_user_id = user_id
        count.cancelled_at = datetime.now(timezone.utc)
        count.cancellation_reason = reason

        return count

    return run_with_retry(_op)


def get_count_summary(count_id: int) -> dict:
    """
    Get count summary with lines.

    Args:
        count_id: Count document ID

    Returns:
        dict: Count summary with lines

    Raises:
        CountError: If count not found
    """
    count = db.session.query(Count).get(count_id)
    if not count:
        raise CountError(f"Count {count_id} not found")

    return {
        **count.to_dict(),
        "lines": [line.to_dict() for line in count.lines],
    }
