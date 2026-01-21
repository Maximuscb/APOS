# Overview: Service-layer operations for vendors; encapsulates business logic and database work.

"""
Vendor Service

WHY: Vendors are first-class entities required for all inventory receives.
Every receive document must have exactly one vendor, regardless of source
(purchase, donation, found stock, etc.).

MULTI-TENANT: Vendors are scoped to organizations via org_id.
Vendor codes are unique within an organization when specified.

DESIGN:
- Products may be sourced from multiple vendors (no required join)
- Vendor-product relationships are implicit via ReceiveDocument history
- Vendor is stored on receive document header, not per line item
"""

from ..extensions import db
from ..models import Vendor, Organization
from .ledger_service import append_ledger_event
from app.time_utils import utcnow


class VendorNotFoundError(Exception):
    """Raised when a vendor is not found."""
    pass


class VendorValidationError(Exception):
    """Raised when vendor data fails validation."""
    pass


def create_vendor(
    *,
    org_id: int,
    name: str,
    code: str | None = None,
    contact_name: str | None = None,
    contact_email: str | None = None,
    contact_phone: str | None = None,
    address: str | None = None,
    notes: str | None = None,
    created_by_user_id: int | None = None,
) -> Vendor:
    """
    Create a new vendor.

    Args:
        org_id: Organization ID (required)
        name: Vendor name (required)
        code: Optional short code for quick lookup (unique within org)
        contact_name: Primary contact name
        contact_email: Contact email
        contact_phone: Contact phone
        address: Vendor address
        notes: Additional notes
        created_by_user_id: User creating the vendor (for audit)

    Returns:
        Created Vendor object

    Raises:
        VendorValidationError: If validation fails (e.g., duplicate code)
    """
    # Validate organization exists
    org = db.session.query(Organization).filter_by(id=org_id).first()
    if not org:
        raise VendorValidationError("Organization not found")
    if not org.is_active:
        raise VendorValidationError("Organization is not active")

    # Validate name
    if not name or not name.strip():
        raise VendorValidationError("Vendor name is required")
    name = name.strip()

    # Normalize code
    if code:
        code = code.strip().upper()
        if not code:
            code = None

    # Check for duplicate code within organization
    if code:
        existing = db.session.query(Vendor).filter(
            Vendor.org_id == org_id,
            Vendor.code == code,
            Vendor.is_active.is_(True),
        ).first()
        if existing:
            raise VendorValidationError(f"Vendor code '{code}' already exists in this organization")

    vendor = Vendor(
        org_id=org_id,
        name=name,
        code=code,
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        address=address,
        notes=notes,
        is_active=True,
    )

    db.session.add(vendor)
    db.session.flush()

    # Emit ledger event
    # Note: Vendors are org-level, so we use org's first store or None for store_id
    # In practice, this should be associated with the store context of the operation
    first_store = org.stores[0] if org.stores else None
    if first_store:
        append_ledger_event(
            store_id=first_store.id,
            event_type="vendor.created",
            event_category="vendor",
            entity_type="vendor",
            entity_id=vendor.id,
            actor_user_id=created_by_user_id,
            occurred_at=utcnow(),
        )

    db.session.commit()
    return vendor


def update_vendor(
    *,
    vendor_id: int,
    name: str | None = None,
    code: str | None = None,
    contact_name: str | None = None,
    contact_email: str | None = None,
    contact_phone: str | None = None,
    address: str | None = None,
    notes: str | None = None,
    updated_by_user_id: int | None = None,
) -> Vendor:
    """
    Update an existing vendor.

    Args:
        vendor_id: Vendor ID to update
        name: New vendor name (if provided)
        code: New vendor code (if provided)
        contact_*: Contact information updates
        notes: Notes update
        updated_by_user_id: User performing the update

    Returns:
        Updated Vendor object

    Raises:
        VendorNotFoundError: If vendor not found
        VendorValidationError: If validation fails
    """
    vendor = db.session.query(Vendor).filter_by(id=vendor_id).first()
    if not vendor:
        raise VendorNotFoundError(f"Vendor {vendor_id} not found")
    if not vendor.is_active:
        raise VendorValidationError("Cannot update inactive vendor")

    # Update name if provided
    if name is not None:
        name = name.strip()
        if not name:
            raise VendorValidationError("Vendor name cannot be empty")
        vendor.name = name

    # Update code if provided
    if code is not None:
        if code:
            code = code.strip().upper()
            # Check for duplicate code
            existing = db.session.query(Vendor).filter(
                Vendor.org_id == vendor.org_id,
                Vendor.code == code,
                Vendor.id != vendor_id,
                Vendor.is_active.is_(True),
            ).first()
            if existing:
                raise VendorValidationError(f"Vendor code '{code}' already exists in this organization")
            vendor.code = code
        else:
            vendor.code = None

    # Update contact information if provided
    if contact_name is not None:
        vendor.contact_name = contact_name
    if contact_email is not None:
        vendor.contact_email = contact_email
    if contact_phone is not None:
        vendor.contact_phone = contact_phone
    if address is not None:
        vendor.address = address
    if notes is not None:
        vendor.notes = notes

    db.session.flush()

    # Emit ledger event
    org = vendor.organization
    first_store = org.stores[0] if org.stores else None
    if first_store:
        append_ledger_event(
            store_id=first_store.id,
            event_type="vendor.updated",
            event_category="vendor",
            entity_type="vendor",
            entity_id=vendor.id,
            actor_user_id=updated_by_user_id,
            occurred_at=utcnow(),
        )

    db.session.commit()
    return vendor


def get_vendor(vendor_id: int) -> Vendor:
    """
    Get a vendor by ID.

    Args:
        vendor_id: Vendor ID

    Returns:
        Vendor object

    Raises:
        VendorNotFoundError: If vendor not found
    """
    vendor = db.session.query(Vendor).filter_by(id=vendor_id).first()
    if not vendor:
        raise VendorNotFoundError(f"Vendor {vendor_id} not found")
    return vendor


def get_vendor_by_code(org_id: int, code: str) -> Vendor | None:
    """
    Get a vendor by organization and code.

    Args:
        org_id: Organization ID
        code: Vendor code (case-insensitive)

    Returns:
        Vendor object or None if not found
    """
    if not code:
        return None
    code = code.strip().upper()
    return db.session.query(Vendor).filter(
        Vendor.org_id == org_id,
        Vendor.code == code,
        Vendor.is_active.is_(True),
    ).first()


def list_vendors(
    org_id: int,
    *,
    include_inactive: bool = False,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Vendor], int]:
    """
    List vendors for an organization.

    Args:
        org_id: Organization ID
        include_inactive: If True, include inactive vendors
        search: Optional search term for name or code
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        Tuple of (list of Vendor objects, total count)
    """
    query = db.session.query(Vendor).filter(Vendor.org_id == org_id)

    if not include_inactive:
        query = query.filter(Vendor.is_active.is_(True))

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Vendor.name.ilike(search_term),
                Vendor.code.ilike(search_term),
            )
        )

    # Get total count before pagination
    total = query.count()

    # Apply ordering and pagination
    query = query.order_by(Vendor.name.asc())
    query = query.offset(offset).limit(limit)

    return query.all(), total


def deactivate_vendor(
    vendor_id: int,
    *,
    deactivated_by_user_id: int | None = None,
) -> Vendor:
    """
    Deactivate a vendor (soft delete).

    Args:
        vendor_id: Vendor ID to deactivate
        deactivated_by_user_id: User performing the deactivation

    Returns:
        Deactivated Vendor object

    Raises:
        VendorNotFoundError: If vendor not found
        VendorValidationError: If vendor already inactive
    """
    vendor = db.session.query(Vendor).filter_by(id=vendor_id).first()
    if not vendor:
        raise VendorNotFoundError(f"Vendor {vendor_id} not found")
    if not vendor.is_active:
        raise VendorValidationError("Vendor is already inactive")

    vendor.is_active = False
    db.session.flush()

    # Emit ledger event
    org = vendor.organization
    first_store = org.stores[0] if org.stores else None
    if first_store:
        append_ledger_event(
            store_id=first_store.id,
            event_type="vendor.deactivated",
            event_category="vendor",
            entity_type="vendor",
            entity_id=vendor.id,
            actor_user_id=deactivated_by_user_id,
            occurred_at=utcnow(),
        )

    db.session.commit()
    return vendor


def reactivate_vendor(
    vendor_id: int,
    *,
    reactivated_by_user_id: int | None = None,
) -> Vendor:
    """
    Reactivate an inactive vendor.

    Args:
        vendor_id: Vendor ID to reactivate
        reactivated_by_user_id: User performing the reactivation

    Returns:
        Reactivated Vendor object

    Raises:
        VendorNotFoundError: If vendor not found
        VendorValidationError: If vendor already active
    """
    vendor = db.session.query(Vendor).filter_by(id=vendor_id).first()
    if not vendor:
        raise VendorNotFoundError(f"Vendor {vendor_id} not found")
    if vendor.is_active:
        raise VendorValidationError("Vendor is already active")

    vendor.is_active = True
    db.session.flush()

    # Emit ledger event
    org = vendor.organization
    first_store = org.stores[0] if org.stores else None
    if first_store:
        append_ledger_event(
            store_id=first_store.id,
            event_type="vendor.reactivated",
            event_category="vendor",
            entity_type="vendor",
            entity_id=vendor.id,
            actor_user_id=reactivated_by_user_id,
            occurred_at=utcnow(),
        )

    db.session.commit()
    return vendor


def validate_vendor_for_org(vendor_id: int, org_id: int) -> Vendor:
    """
    Validate that a vendor exists and belongs to the specified organization.

    Args:
        vendor_id: Vendor ID
        org_id: Expected organization ID

    Returns:
        Vendor object if valid

    Raises:
        VendorNotFoundError: If vendor not found
        VendorValidationError: If vendor belongs to different org or is inactive
    """
    vendor = db.session.query(Vendor).filter_by(id=vendor_id).first()
    if not vendor:
        raise VendorNotFoundError(f"Vendor {vendor_id} not found")
    if vendor.org_id != org_id:
        raise VendorValidationError("Vendor does not belong to this organization")
    if not vendor.is_active:
        raise VendorValidationError("Vendor is inactive")
    return vendor
