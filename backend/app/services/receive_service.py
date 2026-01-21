# Overview: Service-layer operations for receive documents; encapsulates business logic.

"""
Receive Document Service

WHY: Document-first inventory receiving with required vendor.
Every receive document must have exactly one vendor, regardless of source.

LIFECYCLE:
1. DRAFT: Created, lines being added
2. APPROVED: Manager approved, ready to post
3. POSTED: Posted to inventory ledger (creates InventoryTransactions)
4. CANCELLED: Cancelled before posting

IMMUTABLE: Once POSTED, document cannot be modified.

DESIGN:
- Vendor is REQUIRED on the document header
- receive_type tracks source: PURCHASE, DONATION, FOUND, TRANSFER_IN, OTHER
- Posting creates individual InventoryTransaction records for each line
"""

from datetime import datetime, timedelta
from sqlalchemy import func

from ..extensions import db
from ..models import (
    ReceiveDocument,
    ReceiveDocumentLine,
    Product,
    Store,
    Vendor,
    InventoryTransaction,
)
from .vendor_service import validate_vendor_for_org
from .inventory_service import receive_inventory
from .document_service import next_document_number
from .ledger_service import append_ledger_event
from app.time_utils import utcnow, parse_iso_datetime


# Valid receive types
RECEIVE_TYPES = {"PURCHASE", "DONATION", "FOUND", "TRANSFER_IN", "OTHER"}

# Valid statuses
STATUS_DRAFT = "DRAFT"
STATUS_APPROVED = "APPROVED"
STATUS_POSTED = "POSTED"
STATUS_CANCELLED = "CANCELLED"


class ReceiveDocumentNotFoundError(Exception):
    """Raised when a receive document is not found."""
    pass


class ReceiveDocumentValidationError(Exception):
    """Raised when receive document data fails validation."""
    pass


class ReceiveDocumentStateError(Exception):
    """Raised when an operation is invalid for the current document state."""
    pass


def _get_store_org_id(store_id: int) -> int:
    """Get the org_id for a store."""
    store = db.session.query(Store).filter_by(id=store_id).first()
    if not store:
        raise ReceiveDocumentValidationError(f"Store {store_id} not found")
    return store.org_id


def _parse_occurred_at(value) -> datetime:
    """Parse occurred_at value to UTC-naive datetime."""
    if value is None:
        return utcnow()

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            from datetime import timezone
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    if isinstance(value, str):
        dt = parse_iso_datetime(value)
        if dt is None:
            raise ReceiveDocumentValidationError("Invalid occurred_at format")
        return dt

    raise ReceiveDocumentValidationError("Invalid occurred_at format")


def create_receive_document(
    *,
    store_id: int,
    vendor_id: int,
    receive_type: str,
    created_by_user_id: int,
    occurred_at: datetime | str | None = None,
    reference_number: str | None = None,
    notes: str | None = None,
) -> ReceiveDocument:
    """
    Create a new receive document.

    Args:
        store_id: Store receiving the inventory
        vendor_id: Vendor providing the inventory (REQUIRED)
        receive_type: Type of receive (PURCHASE, DONATION, FOUND, etc.)
        created_by_user_id: User creating the document
        occurred_at: Business date/time of the receive
        reference_number: PO number, invoice number, etc.
        notes: Additional notes

    Returns:
        Created ReceiveDocument object

    Raises:
        ReceiveDocumentValidationError: If validation fails
    """
    # Validate receive type
    if receive_type not in RECEIVE_TYPES:
        raise ReceiveDocumentValidationError(
            f"Invalid receive_type. Must be one of: {', '.join(RECEIVE_TYPES)}"
        )

    # Get store's org_id
    org_id = _get_store_org_id(store_id)

    # Validate vendor belongs to this org
    try:
        validate_vendor_for_org(vendor_id, org_id)
    except Exception as e:
        raise ReceiveDocumentValidationError(str(e))

    # Parse occurred_at
    occurred_dt = _parse_occurred_at(occurred_at)

    # Validate not in future
    now = utcnow()
    if occurred_dt > (now + timedelta(minutes=2)):
        raise ReceiveDocumentValidationError("occurred_at cannot be in the future")

    # Generate document number
    doc_number = next_document_number(
        store_id=store_id,
        document_type="RECEIVE",
        prefix="RCV",
    )

    doc = ReceiveDocument(
        store_id=store_id,
        vendor_id=vendor_id,
        document_number=doc_number,
        receive_type=receive_type,
        status=STATUS_DRAFT,
        occurred_at=occurred_dt,
        reference_number=reference_number,
        notes=notes,
        created_by_user_id=created_by_user_id,
    )

    db.session.add(doc)
    db.session.flush()

    # Emit ledger event
    append_ledger_event(
        store_id=store_id,
        event_type="receive.created",
        event_category="receive",
        entity_type="receive_document",
        entity_id=doc.id,
        actor_user_id=created_by_user_id,
        occurred_at=occurred_dt,
        note=f"Receive document {doc_number} created",
    )

    db.session.commit()
    return doc


def get_receive_document(document_id: int) -> ReceiveDocument:
    """
    Get a receive document by ID.

    Args:
        document_id: Document ID

    Returns:
        ReceiveDocument object

    Raises:
        ReceiveDocumentNotFoundError: If not found
    """
    doc = db.session.query(ReceiveDocument).filter_by(id=document_id).first()
    if not doc:
        raise ReceiveDocumentNotFoundError(f"Receive document {document_id} not found")
    return doc


def get_receive_document_by_number(store_id: int, document_number: str) -> ReceiveDocument | None:
    """Get a receive document by store and document number."""
    return db.session.query(ReceiveDocument).filter(
        ReceiveDocument.store_id == store_id,
        ReceiveDocument.document_number == document_number,
    ).first()


def add_receive_line(
    *,
    document_id: int,
    product_id: int,
    quantity: int,
    unit_cost_cents: int,
    note: str | None = None,
) -> ReceiveDocumentLine:
    """
    Add a line item to a receive document.

    Args:
        document_id: Document to add line to
        product_id: Product being received
        quantity: Quantity (must be positive)
        unit_cost_cents: Unit cost in cents
        note: Optional note for this line

    Returns:
        Created ReceiveDocumentLine object

    Raises:
        ReceiveDocumentNotFoundError: If document not found
        ReceiveDocumentStateError: If document is not in DRAFT status
        ReceiveDocumentValidationError: If validation fails
    """
    doc = get_receive_document(document_id)

    # Only DRAFT documents can have lines added
    if doc.status != STATUS_DRAFT:
        raise ReceiveDocumentStateError(
            f"Cannot add lines to {doc.status} document. Only DRAFT documents can be modified."
        )

    # Validate quantity
    if quantity <= 0:
        raise ReceiveDocumentValidationError("Quantity must be positive")

    # Validate unit cost
    if unit_cost_cents < 0:
        raise ReceiveDocumentValidationError("Unit cost cannot be negative")

    # Validate product exists and belongs to the store
    product = db.session.query(Product).filter_by(id=product_id).first()
    if not product:
        raise ReceiveDocumentValidationError(f"Product {product_id} not found")
    if product.store_id != doc.store_id:
        raise ReceiveDocumentValidationError("Product does not belong to this store")
    if not product.is_active:
        raise ReceiveDocumentValidationError("Product is inactive")

    # Check for duplicate product in document
    existing = db.session.query(ReceiveDocumentLine).filter(
        ReceiveDocumentLine.receive_document_id == document_id,
        ReceiveDocumentLine.product_id == product_id,
    ).first()
    if existing:
        raise ReceiveDocumentValidationError(
            f"Product {product.sku} already exists in this document. Update the existing line instead."
        )

    line = ReceiveDocumentLine(
        receive_document_id=document_id,
        product_id=product_id,
        quantity=quantity,
        unit_cost_cents=unit_cost_cents,
        line_cost_cents=quantity * unit_cost_cents,
        note=note,
    )

    db.session.add(line)
    db.session.commit()
    return line


def update_receive_line(
    *,
    line_id: int,
    quantity: int | None = None,
    unit_cost_cents: int | None = None,
    note: str | None = None,
) -> ReceiveDocumentLine:
    """
    Update a line item on a receive document.

    Args:
        line_id: Line ID to update
        quantity: New quantity (if provided)
        unit_cost_cents: New unit cost (if provided)
        note: New note (if provided)

    Returns:
        Updated ReceiveDocumentLine object

    Raises:
        ReceiveDocumentNotFoundError: If line not found
        ReceiveDocumentStateError: If document is not DRAFT
        ReceiveDocumentValidationError: If validation fails
    """
    line = db.session.query(ReceiveDocumentLine).filter_by(id=line_id).first()
    if not line:
        raise ReceiveDocumentNotFoundError(f"Line {line_id} not found")

    doc = line.receive_document
    if doc.status != STATUS_DRAFT:
        raise ReceiveDocumentStateError(
            f"Cannot modify lines on {doc.status} document"
        )

    if quantity is not None:
        if quantity <= 0:
            raise ReceiveDocumentValidationError("Quantity must be positive")
        line.quantity = quantity

    if unit_cost_cents is not None:
        if unit_cost_cents < 0:
            raise ReceiveDocumentValidationError("Unit cost cannot be negative")
        line.unit_cost_cents = unit_cost_cents

    if note is not None:
        line.note = note

    # Recalculate line cost
    line.line_cost_cents = line.quantity * line.unit_cost_cents

    db.session.commit()
    return line


def remove_receive_line(line_id: int) -> None:
    """
    Remove a line item from a receive document.

    Args:
        line_id: Line ID to remove

    Raises:
        ReceiveDocumentNotFoundError: If line not found
        ReceiveDocumentStateError: If document is not DRAFT
    """
    line = db.session.query(ReceiveDocumentLine).filter_by(id=line_id).first()
    if not line:
        raise ReceiveDocumentNotFoundError(f"Line {line_id} not found")

    doc = line.receive_document
    if doc.status != STATUS_DRAFT:
        raise ReceiveDocumentStateError(
            f"Cannot remove lines from {doc.status} document"
        )

    db.session.delete(line)
    db.session.commit()


def approve_receive_document(
    document_id: int,
    approved_by_user_id: int,
) -> ReceiveDocument:
    """
    Approve a receive document.

    Args:
        document_id: Document to approve
        approved_by_user_id: User approving the document

    Returns:
        Approved ReceiveDocument object

    Raises:
        ReceiveDocumentNotFoundError: If not found
        ReceiveDocumentStateError: If not in DRAFT status
        ReceiveDocumentValidationError: If document has no lines
    """
    doc = get_receive_document(document_id)

    if doc.status != STATUS_DRAFT:
        raise ReceiveDocumentStateError(
            f"Cannot approve {doc.status} document. Only DRAFT documents can be approved."
        )

    # Ensure document has lines
    if not doc.lines:
        raise ReceiveDocumentValidationError(
            "Cannot approve document with no line items"
        )

    doc.status = STATUS_APPROVED
    doc.approved_by_user_id = approved_by_user_id
    doc.approved_at = utcnow()

    db.session.flush()

    append_ledger_event(
        store_id=doc.store_id,
        event_type="receive.approved",
        event_category="receive",
        entity_type="receive_document",
        entity_id=doc.id,
        actor_user_id=approved_by_user_id,
        occurred_at=utcnow(),
        note=f"Receive document {doc.document_number} approved",
    )

    db.session.commit()
    return doc


def post_receive_document(
    document_id: int,
    posted_by_user_id: int,
) -> ReceiveDocument:
    """
    Post a receive document to inventory.

    Creates InventoryTransaction records for each line item.

    Args:
        document_id: Document to post
        posted_by_user_id: User posting the document

    Returns:
        Posted ReceiveDocument object

    Raises:
        ReceiveDocumentNotFoundError: If not found
        ReceiveDocumentStateError: If not in APPROVED status
    """
    doc = get_receive_document(document_id)

    if doc.status != STATUS_APPROVED:
        raise ReceiveDocumentStateError(
            f"Cannot post {doc.status} document. Only APPROVED documents can be posted."
        )

    now = utcnow()

    # Create inventory transactions for each line
    for line in doc.lines:
        # Create the inventory transaction
        tx = InventoryTransaction(
            store_id=doc.store_id,
            product_id=line.product_id,
            type="RECEIVE",
            quantity_delta=line.quantity,
            unit_cost_cents=line.unit_cost_cents,
            note=f"From receive {doc.document_number}" + (f": {line.note}" if line.note else ""),
            occurred_at=doc.occurred_at,
            status="POSTED",
            posted_by_user_id=posted_by_user_id,
            posted_at=now,
        )
        db.session.add(tx)
        db.session.flush()

        # Link the line to the transaction
        line.inventory_transaction_id = tx.id

        # Emit inventory ledger event
        append_ledger_event(
            store_id=doc.store_id,
            event_type="inventory.received",
            event_category="inventory",
            entity_type="inventory_transaction",
            entity_id=tx.id,
            actor_user_id=posted_by_user_id,
            occurred_at=doc.occurred_at,
            note=tx.note,
        )

    # Update document status
    doc.status = STATUS_POSTED
    doc.posted_by_user_id = posted_by_user_id
    doc.posted_at = now

    db.session.flush()

    append_ledger_event(
        store_id=doc.store_id,
        event_type="receive.posted",
        event_category="receive",
        entity_type="receive_document",
        entity_id=doc.id,
        actor_user_id=posted_by_user_id,
        occurred_at=now,
        note=f"Receive document {doc.document_number} posted with {len(doc.lines)} lines",
    )

    db.session.commit()
    return doc


def cancel_receive_document(
    document_id: int,
    cancelled_by_user_id: int,
    reason: str,
) -> ReceiveDocument:
    """
    Cancel a receive document.

    Args:
        document_id: Document to cancel
        cancelled_by_user_id: User cancelling the document
        reason: Reason for cancellation

    Returns:
        Cancelled ReceiveDocument object

    Raises:
        ReceiveDocumentNotFoundError: If not found
        ReceiveDocumentStateError: If already POSTED or CANCELLED
    """
    doc = get_receive_document(document_id)

    if doc.status == STATUS_POSTED:
        raise ReceiveDocumentStateError(
            "Cannot cancel POSTED document. Create an adjustment instead."
        )
    if doc.status == STATUS_CANCELLED:
        raise ReceiveDocumentStateError("Document is already cancelled")

    doc.status = STATUS_CANCELLED
    doc.cancelled_by_user_id = cancelled_by_user_id
    doc.cancelled_at = utcnow()
    doc.cancellation_reason = reason

    db.session.flush()

    append_ledger_event(
        store_id=doc.store_id,
        event_type="receive.cancelled",
        event_category="receive",
        entity_type="receive_document",
        entity_id=doc.id,
        actor_user_id=cancelled_by_user_id,
        occurred_at=utcnow(),
        note=f"Receive document {doc.document_number} cancelled: {reason}",
    )

    db.session.commit()
    return doc


def list_receive_documents(
    store_id: int,
    *,
    status: str | None = None,
    vendor_id: int | None = None,
    receive_type: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ReceiveDocument], int]:
    """
    List receive documents for a store.

    Args:
        store_id: Store ID
        status: Filter by status
        vendor_id: Filter by vendor
        receive_type: Filter by receive type
        from_date: Filter by occurred_at >= from_date
        to_date: Filter by occurred_at <= to_date
        limit: Maximum results
        offset: Pagination offset

    Returns:
        Tuple of (list of documents, total count)
    """
    query = db.session.query(ReceiveDocument).filter(
        ReceiveDocument.store_id == store_id
    )

    if status:
        query = query.filter(ReceiveDocument.status == status)
    if vendor_id:
        query = query.filter(ReceiveDocument.vendor_id == vendor_id)
    if receive_type:
        query = query.filter(ReceiveDocument.receive_type == receive_type)
    if from_date:
        query = query.filter(ReceiveDocument.occurred_at >= from_date)
    if to_date:
        query = query.filter(ReceiveDocument.occurred_at <= to_date)

    total = query.count()

    query = query.order_by(ReceiveDocument.created_at.desc())
    query = query.offset(offset).limit(limit)

    return query.all(), total


def get_receive_document_with_lines(document_id: int) -> dict:
    """
    Get a receive document with its line items.

    Returns dict with document data and lines array.
    """
    doc = get_receive_document(document_id)

    result = doc.to_dict()
    result["lines"] = [line.to_dict() for line in doc.lines]
    result["vendor"] = doc.vendor.to_dict() if doc.vendor else None

    # Calculate totals
    result["total_quantity"] = sum(line.quantity for line in doc.lines)
    result["total_cost_cents"] = sum(line.line_cost_cents for line in doc.lines)

    return result
