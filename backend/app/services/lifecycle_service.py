# Overview: Service-layer operations for lifecycle; encapsulates business logic and database work.

"""
APOS Document Lifecycle Service ()

================================================================================
PURPOSE: Enforce Draft -> Approved -> Posted lifecycle for inventory transactions
================================================================================

WHY THIS EXISTS:
- Prevents accidental posting of data entry errors
- Enables review workflows (manager approval for adjustments)
- Allows AI-generated drafts later without financial risk
- Maintains audit trail of approvals and postings
- Supports threshold-based controls (future: large adjustments require approval)

STATE MACHINE:
    DRAFT -> APPROVED -> POSTED

    DRAFT:    Data entry, can be edited/deleted, does NOT affect inventory
    APPROVED: Reviewed, ready to post, but NOT yet affecting inventory
    POSTED:   IMMUTABLE, affects inventory calculations, appends to master ledger

RULES (NON-NEGOTIABLE):
1. Cannot skip states (DRAFT -> POSTED is forbidden)
2. Cannot reverse states (POSTED -> APPROVED is forbidden)
3. Only POSTED transactions affect inventory calculations
4. POSTED transactions are immutable (cannot be edited/deleted)
5. Master ledger events are created ONLY on posting, not on draft/approval

FUTURE EXTENSIONS:
- User-based authorization (requires Auth)
- Threshold-based approval requirements (e.g., >$1000 adjustments)
- Manager override workflows
- Automatic approval for low-risk transactions (e.g., POS sales)
- Bulk approval operations

================================================================================
"""

from __future__ import annotations
from typing import Literal

from ..extensions import db
from ..models import InventoryTransaction
from app.time_utils import utcnow


# Valid lifecycle states (must match models.py)
VALID_STATUSES = {"DRAFT", "APPROVED", "POSTED"}
LifecycleStatus = Literal["DRAFT", "APPROVED", "POSTED"]


class LifecycleError(ValueError):
    """
    Raised when an invalid lifecycle transition is attempted.

    This is a domain error, not a technical error. It indicates
    that the user attempted an operation that violates business rules.
    """
    pass


def validate_status(status: str) -> None:
    """
    Validate that a status value is one of the allowed states.

    Args:
        status: The status string to validate

    Raises:
        LifecycleError: If status is not in VALID_STATUSES

    WHY: Centralizes validation to prevent typos and invalid states.
    """
    if status not in VALID_STATUSES:
        raise LifecycleError(
            f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )


def can_transition(from_status: str, to_status: str) -> bool:
    """
    Check if a state transition is valid according to the lifecycle rules.

    Valid transitions:
    - DRAFT -> APPROVED
    - APPROVED -> POSTED

    Invalid transitions:
    - DRAFT -> POSTED (must go through APPROVED)
    - POSTED -> anything (POSTED is terminal and immutable)
    - APPROVED -> DRAFT (no backwards movement)
    - Any transition to the same state (no-op should be handled by caller)

    Args:
        from_status: Current status
        to_status: Desired status

    Returns:
        True if transition is allowed, False otherwise

    WHY: Enforces the non-negotiable state machine rules.
    """
    validate_status(from_status)
    validate_status(to_status)

    # No-op transitions should be handled by caller, but technically allowed
    if from_status == to_status:
        return True

    # Define the only valid forward transitions
    valid_transitions = {
        ("DRAFT", "APPROVED"),
        ("APPROVED", "POSTED"),
    }

    return (from_status, to_status) in valid_transitions


def approve_transaction(
    transaction_id: int,
    *,
    approved_by_user_id: int | None = None,
) -> InventoryTransaction:
    """
    Approve a DRAFT transaction (DRAFT -> APPROVED).

    WHY: Approval indicates that a transaction has been reviewed and is
    ready to be posted. This is the checkpoint before affecting inventory.

    Args:
        transaction_id: ID of the transaction to approve
        approved_by_user_id: ID of the user approving (None until User model exists)

    Returns:
        The approved transaction

    Raises:
        ValueError: If transaction not found
        LifecycleError: If transaction is not in DRAFT status

    DESIGN NOTES:
    - Currently accepts approved_by_user_id=None because User model doesn't exist yet
    - Once User model is implemented, this should be required
    - Approval does NOT affect inventory calculations (only POSTED does)
    - Approval does NOT create master ledger events (only POSTED does)
    - Approval timestamp is recorded for audit trail
    """
    tx = db.session.query(InventoryTransaction).get(transaction_id)
    if tx is None:
        raise ValueError(f"InventoryTransaction {transaction_id} not found")

    if tx.status != "DRAFT":
        raise LifecycleError(
            f"Cannot approve transaction {transaction_id}: "
            f"current status is '{tx.status}', must be 'DRAFT'"
        )

    # Perform state transition
    tx.status = "APPROVED"
    tx.approved_by_user_id = approved_by_user_id
    tx.approved_at = utcnow()

    db.session.commit()
    return tx


def post_transaction(
    transaction_id: int,
    *,
    posted_by_user_id: int | None = None,
) -> InventoryTransaction:
    """
    Post an APPROVED transaction (APPROVED -> POSTED).

    WHY: Posting finalizes the transaction and makes it affect inventory
    calculations. POSTED transactions are immutable and append to the master ledger.

    Args:
        transaction_id: ID of the transaction to post
        posted_by_user_id: ID of the user posting (None until User model exists)

    Returns:
        The posted transaction

    Raises:
        ValueError: If transaction not found
        LifecycleError: If transaction is not in APPROVED status

    CRITICAL DESIGN NOTES:
    - POSTED transactions become immutable (no edits/deletes)
    - POSTED transactions affect inventory calculations (on-hand qty, WAC)
    - Master ledger event is created ONLY on posting (see inventory_service.py)
    - posted_at timestamp is recorded for audit trail
    - Once POSTED, a transaction cannot be un-posted (must create reversal)

    FUTURE: Master ledger event creation should be handled HERE, not in inventory_service,
    to centralize lifecycle behavior. For now, inventory_service still handles it
    for backwards compatibility.
    """
    tx = db.session.query(InventoryTransaction).get(transaction_id)
    if tx is None:
        raise ValueError(f"InventoryTransaction {transaction_id} not found")

    if tx.status != "APPROVED":
        raise LifecycleError(
            f"Cannot post transaction {transaction_id}: "
            f"current status is '{tx.status}', must be 'APPROVED'"
        )

    # Perform state transition
    tx.status = "POSTED"
    tx.posted_by_user_id = posted_by_user_id
    tx.posted_at = utcnow()

    db.session.commit()

    # TODO (): Create master ledger event here instead of inventory_service
    # This would centralize all lifecycle behavior in one place

    return tx


def can_edit_transaction(tx: InventoryTransaction) -> bool:
    """
    Check if a transaction can be edited based on its lifecycle status.

    Rules:
    - DRAFT: Can be edited
    - APPROVED: Cannot be edited (must un-approve to DRAFT first)
    - POSTED: Cannot be edited (immutable)

    Args:
        tx: The transaction to check

    Returns:
        True if transaction can be edited, False otherwise

    WHY: Centralizes the logic for determining if a transaction is mutable.
    Used by edit/update endpoints to enforce immutability.
    """
    return tx.status == "DRAFT"


def can_delete_transaction(tx: InventoryTransaction) -> bool:
    """
    Check if a transaction can be deleted based on its lifecycle status.

    Rules:
    - DRAFT: Can be deleted
    - APPROVED: Can be deleted (but should require authorization)
    - POSTED: Cannot be deleted (immutable, must create reversal)

    Args:
        tx: The transaction to check

    Returns:
        True if transaction can be deleted, False otherwise

    WHY: POSTED transactions are immutable and must remain for audit trail.
    If a POSTED transaction is incorrect, create a reversal transaction instead.
    """
    return tx.status in ("DRAFT", "APPROVED")


def get_transactions_by_status(
    store_id: int,
    status: LifecycleStatus,
    *,
    product_id: int | None = None,
    limit: int = 200,
) -> list[InventoryTransaction]:
    """
    Query inventory transactions by lifecycle status.

    WHY: Enables UI to show:
    - Pending drafts that need approval
    - Approved transactions ready to post
    - Posted transactions (audit history)

    Args:
        store_id: Store to query
        status: Lifecycle status to filter by
        product_id: Optional product filter
        limit: Maximum results

    Returns:
        List of transactions matching the criteria

    USAGE EXAMPLES:
    - Show "Pending Approval" queue: get_transactions_by_status(store_id, "DRAFT")
    - Show "Ready to Post" queue: get_transactions_by_status(store_id, "APPROVED")
    - Show posted history: get_transactions_by_status(store_id, "POSTED")
    """
    validate_status(status)

    q = InventoryTransaction.query.filter_by(
        store_id=store_id,
        status=status,
    )

    if product_id is not None:
        q = q.filter_by(product_id=product_id)

    q = q.order_by(
        InventoryTransaction.occurred_at.desc(),
        InventoryTransaction.id.desc(),
    )

    return q.limit(limit).all()


# ================================================================================
# BATCH OPERATIONS (Future)
# ================================================================================
# These are stubs for future implementation. Batch operations are useful for:
# - Approving multiple transactions at once (e.g., daily receiving)
# - Posting end-of-day sales
# - Manager approval workflows
# ================================================================================

def approve_transactions_batch(
    transaction_ids: list[int],
    *,
    approved_by_user_id: int | None = None,
) -> tuple[list[InventoryTransaction], list[tuple[int, str]]]:
    """
    Approve multiple transactions in a single operation.

    WHY: Manager needs to approve a batch of receiving transactions at once.

    Returns:
        Tuple of (successful_transactions, failed_ids_with_errors)

    NOT IMPLEMENTED YET - placeholder for future enhancement.
    """
    raise NotImplementedError("Batch approval not yet implemented")


def post_transactions_batch(
    transaction_ids: list[int],
    *,
    posted_by_user_id: int | None = None,
) -> tuple[list[InventoryTransaction], list[tuple[int, str]]]:
    """
    Post multiple approved transactions in a single operation.

    WHY: Posting end-of-day sales or approved adjustments as a batch.

    Returns:
        Tuple of (successful_transactions, failed_ids_with_errors)

    NOT IMPLEMENTED YET - placeholder for future enhancement.
    """
    raise NotImplementedError("Batch posting not yet implemented")
