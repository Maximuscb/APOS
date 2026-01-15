"""
Phase 10: Return Processing Service

WHY: Retail returns are common and require careful accounting. The critical
challenge is COGS reversal: we must credit the ORIGINAL sale cost, not the
current weighted average cost.

DESIGN PRINCIPLES:
- Returns reference original Sale for traceability
- Manager approval required before processing
- COGS reversal uses original `unit_cost_cents_at_sale` from sale transaction
- Inventory restored via RETURN transaction type
- Restocking fees optional (deducted from refund)
- Immutable audit trail (cannot modify completed returns)

LIFECYCLE:
1. Create return (PENDING) - Customer initiates return
2. Approve/Reject (manager decision)
3. Complete return (APPROVED → COMPLETED) - Process return, restore inventory, issue refund
"""

from ..extensions import db
from ..models import Return, ReturnLine, Sale, SaleLine, InventoryTransaction
from app.time_utils import utcnow
from sqlalchemy import and_


class ReturnError(Exception):
    """Raised for return operation errors."""
    pass


# =============================================================================
# RETURN STATUS CONSTANTS
# =============================================================================

RETURN_STATUS_PENDING = "PENDING"
RETURN_STATUS_APPROVED = "APPROVED"
RETURN_STATUS_COMPLETED = "COMPLETED"
RETURN_STATUS_REJECTED = "REJECTED"


# =============================================================================
# RETURN CREATION
# =============================================================================

def create_return(
    original_sale_id: int,
    store_id: int,
    user_id: int,
    reason: str | None = None,
    restocking_fee_cents: int = 0,
    register_id: int | None = None,
    register_session_id: int | None = None
) -> Return:
    """
    Create a new return document (status: PENDING).

    WHY: Customer wants to return items from a previous sale.
    Return must reference original sale for traceability and COGS reversal.

    Args:
        original_sale_id: Sale being returned from
        store_id: Store where return is being processed
        user_id: User creating the return
        reason: Customer's reason for return
        restocking_fee_cents: Optional restocking fee (deducted from refund)
        register_id: Register where return initiated
        register_session_id: Session where return initiated

    Returns:
        Return document with PENDING status

    Raises:
        ReturnError: If sale not found or invalid
    """
    # Verify sale exists
    sale = db.session.query(Sale).get(original_sale_id)
    if not sale:
        raise ReturnError(f"Sale {original_sale_id} not found")

    if sale.status != "POSTED":
        raise ReturnError(f"Can only return POSTED sales. Sale {original_sale_id} has status: {sale.status}")

    # Generate document number
    # Count existing returns for store to get next number
    count = db.session.query(Return).filter_by(store_id=store_id).count()
    document_number = f"R-{str(count + 1).zfill(6)}"

    # Create return
    return_doc = Return(
        store_id=store_id,
        document_number=document_number,
        original_sale_id=original_sale_id,
        status=RETURN_STATUS_PENDING,
        reason=reason,
        restocking_fee_cents=restocking_fee_cents,
        created_at=utcnow(),
        created_by_user_id=user_id,
        register_id=register_id,
        register_session_id=register_session_id
    )

    db.session.add(return_doc)
    db.session.commit()

    return return_doc


def add_return_line(
    return_id: int,
    original_sale_line_id: int,
    quantity: int
) -> ReturnLine:
    """
    Add a line item to a return.

    WHY: Specify which items from the original sale are being returned.
    Fetches original price and COGS for refund and accounting.

    Args:
        return_id: Return document
        original_sale_line_id: SaleLine being returned
        quantity: How many units to return

    Returns:
        ReturnLine with refund and COGS info populated

    Raises:
        ReturnError: If return not PENDING, sale line not found, or quantity invalid
    """
    # Get return
    return_doc = db.session.query(Return).get(return_id)
    if not return_doc:
        raise ReturnError(f"Return {return_id} not found")

    if return_doc.status != RETURN_STATUS_PENDING:
        raise ReturnError(f"Can only add lines to PENDING returns. Return {return_id} has status: {return_doc.status}")

    # Get original sale line
    sale_line = db.session.query(SaleLine).get(original_sale_line_id)
    if not sale_line:
        raise ReturnError(f"SaleLine {original_sale_line_id} not found")

    # Verify sale line belongs to the original sale
    if sale_line.sale_id != return_doc.original_sale_id:
        raise ReturnError(f"SaleLine {original_sale_line_id} does not belong to sale {return_doc.original_sale_id}")

    # Validate quantity
    if quantity <= 0:
        raise ReturnError("Return quantity must be positive")

    if quantity > sale_line.quantity:
        raise ReturnError(f"Cannot return {quantity} units. Original sale only had {sale_line.quantity} units.")

    # Check if already returned
    existing_returns = db.session.query(ReturnLine).filter_by(
        original_sale_line_id=original_sale_line_id
    ).join(Return).filter(
        Return.status.in_([RETURN_STATUS_COMPLETED, RETURN_STATUS_APPROVED, RETURN_STATUS_PENDING])
    ).all()

    total_returned = sum(r.quantity for r in existing_returns)
    if total_returned + quantity > sale_line.quantity:
        raise ReturnError(
            f"Cannot return {quantity} units. Original quantity: {sale_line.quantity}, "
            f"already returned: {total_returned}, available: {sale_line.quantity - total_returned}"
        )

    # Get original COGS from inventory transaction
    # CRITICAL: This is the original cost at sale time, not current WAC
    original_inv_txn = db.session.query(InventoryTransaction).get(sale_line.inventory_transaction_id)
    original_unit_cost_cents = None
    original_cogs_cents = None

    if original_inv_txn:
        original_unit_cost_cents = original_inv_txn.unit_cost_cents_at_sale
        # Calculate COGS for returned quantity
        if original_unit_cost_cents:
            original_cogs_cents = original_unit_cost_cents * quantity

    # Calculate refund for this line
    line_refund_cents = sale_line.unit_price_cents * quantity

    # Create return line
    return_line = ReturnLine(
        return_id=return_id,
        original_sale_line_id=original_sale_line_id,
        product_id=sale_line.product_id,
        quantity=quantity,
        unit_price_cents=sale_line.unit_price_cents,
        line_refund_cents=line_refund_cents,
        original_unit_cost_cents=original_unit_cost_cents,
        original_cogs_cents=original_cogs_cents,
        created_at=utcnow()
    )

    db.session.add(return_line)

    # Update return total refund amount
    _update_return_refund_amount(return_id)

    db.session.commit()

    return return_line


# =============================================================================
# RETURN APPROVAL / REJECTION
# =============================================================================

def approve_return(
    return_id: int,
    manager_user_id: int
) -> Return:
    """
    Approve a return (manager action).

    WHY: Returns require manager approval before processing.
    Prevents fraudulent returns and gives management oversight.

    Args:
        return_id: Return to approve
        manager_user_id: Manager approving the return

    Returns:
        Return with APPROVED status

    Raises:
        ReturnError: If return not PENDING
    """
    return_doc = db.session.query(Return).get(return_id)
    if not return_doc:
        raise ReturnError(f"Return {return_id} not found")

    if return_doc.status != RETURN_STATUS_PENDING:
        raise ReturnError(f"Can only approve PENDING returns. Return {return_id} has status: {return_doc.status}")

    # Check that return has lines
    if not return_doc.lines:
        raise ReturnError(f"Cannot approve return {return_id} with no lines")

    # Approve return
    return_doc.status = RETURN_STATUS_APPROVED
    return_doc.approved_at = utcnow()
    return_doc.approved_by_user_id = manager_user_id

    db.session.commit()

    return return_doc


def reject_return(
    return_id: int,
    manager_user_id: int,
    rejection_reason: str
) -> Return:
    """
    Reject a return (manager action).

    WHY: Manager may reject returns for various reasons:
    - Items damaged/used
    - No receipt
    - Outside return window
    - Suspected fraud

    Args:
        return_id: Return to reject
        manager_user_id: Manager rejecting the return
        rejection_reason: Why return is rejected

    Returns:
        Return with REJECTED status

    Raises:
        ReturnError: If return not PENDING
    """
    return_doc = db.session.query(Return).get(return_id)
    if not return_doc:
        raise ReturnError(f"Return {return_id} not found")

    if return_doc.status != RETURN_STATUS_PENDING:
        raise ReturnError(f"Can only reject PENDING returns. Return {return_id} has status: {return_doc.status}")

    # Reject return
    return_doc.status = RETURN_STATUS_REJECTED
    return_doc.rejected_at = utcnow()
    return_doc.rejected_by_user_id = manager_user_id
    return_doc.rejection_reason = rejection_reason

    db.session.commit()

    return return_doc


# =============================================================================
# RETURN COMPLETION (INVENTORY RESTORATION & COGS REVERSAL)
# =============================================================================

def complete_return(
    return_id: int,
    user_id: int
) -> Return:
    """
    Complete a return: restore inventory and reverse COGS.

    WHY: This is where the accounting magic happens. We must:
    1. Restore inventory (create RETURN transactions)
    2. Reverse COGS using ORIGINAL sale cost (not current WAC)
    3. Mark return as COMPLETED

    CRITICAL COGS LOGIC:
    When the sale was originally posted, we recorded:
    - `unit_cost_cents_at_sale`: The WAC at time of sale
    - `cogs_cents`: Total cost of goods sold

    For the return, we CREDIT these exact amounts back to reverse COGS.
    We do NOT use the current WAC, which may have changed.

    Args:
        return_id: Return to complete
        user_id: User completing the return

    Returns:
        Return with COMPLETED status and inventory restored

    Raises:
        ReturnError: If return not APPROVED
    """
    return_doc = db.session.query(Return).get(return_id)
    if not return_doc:
        raise ReturnError(f"Return {return_id} not found")

    if return_doc.status != RETURN_STATUS_APPROVED:
        raise ReturnError(f"Can only complete APPROVED returns. Return {return_id} has status: {return_doc.status}")

    # Process each return line: create RETURN inventory transaction
    for return_line in return_doc.lines:
        # Create RETURN inventory transaction
        # Positive quantity_delta to restore inventory
        inv_txn = InventoryTransaction(
            store_id=return_doc.store_id,
            product_id=return_line.product_id,
            type="RETURN",
            quantity_delta=return_line.quantity,  # Positive: restoring inventory
            unit_cost_cents=None,  # Not a RECEIVE, so no new cost
            note=f"Return from sale {return_doc.original_sale_id}",
            occurred_at=utcnow(),
            status="POSTED",  # Returns are immediately posted
            # Reference to return
            sale_id=str(return_doc.id),  # Using return ID here for traceability
            sale_line_id=str(return_line.id),
            # CRITICAL: Credit original COGS (COGS reversal)
            unit_cost_cents_at_sale=return_line.original_unit_cost_cents,
            cogs_cents=-return_line.original_cogs_cents if return_line.original_cogs_cents else None  # Negative to credit back
        )

        db.session.add(inv_txn)
        db.session.flush()  # Get ID

        # Link return line to inventory transaction
        return_line.inventory_transaction_id = inv_txn.id

    # Mark return as completed
    return_doc.status = RETURN_STATUS_COMPLETED
    return_doc.completed_at = utcnow()
    return_doc.completed_by_user_id = user_id

    db.session.commit()

    return return_doc


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _update_return_refund_amount(return_id: int) -> None:
    """
    Recalculate and update return refund amount.

    Refund = Sum of all return line refunds - restocking fee
    """
    return_doc = db.session.query(Return).get(return_id)
    if not return_doc:
        return

    # Sum all line refunds
    total_line_refund = sum(line.line_refund_cents for line in return_doc.lines)

    # Subtract restocking fee
    refund_amount = total_line_refund - return_doc.restocking_fee_cents

    # Ensure refund is not negative
    refund_amount = max(0, refund_amount)

    return_doc.refund_amount_cents = refund_amount


# =============================================================================
# QUERIES
# =============================================================================

def get_return(return_id: int) -> Return | None:
    """Get return by ID."""
    return db.session.query(Return).get(return_id)


def get_sale_returns(sale_id: int) -> list[Return]:
    """Get all returns for a sale."""
    return db.session.query(Return).filter_by(
        original_sale_id=sale_id
    ).order_by(Return.created_at.desc()).all()


def get_returns_by_status(store_id: int, status: str) -> list[Return]:
    """Get all returns for a store with a given status."""
    return db.session.query(Return).filter_by(
        store_id=store_id,
        status=status
    ).order_by(Return.created_at.desc()).all()


def get_pending_returns(store_id: int) -> list[Return]:
    """Get all pending returns awaiting manager approval."""
    return get_returns_by_status(store_id, RETURN_STATUS_PENDING)


def get_return_summary(return_id: int) -> dict:
    """
    Get comprehensive return summary.

    Returns:
        - return: Return details
        - lines: Return line details
        - original_sale: Original sale info
        - total_refund: Total refund amount
    """
    return_doc = db.session.query(Return).get(return_id)
    if not return_doc:
        raise ReturnError(f"Return {return_id} not found")

    return {
        "return": return_doc.to_dict(),
        "lines": [line.to_dict() for line in return_doc.lines],
        "original_sale": return_doc.original_sale.to_dict() if return_doc.original_sale else None,
        "total_refund_cents": return_doc.refund_amount_cents,
    }
