# Overview: Service-layer operations for identifier; encapsulates business logic and database work.

"""
Identifier Service - First-class identifier lookup

WHY: Prevents silent mis-scans and barcode conflicts. Deterministic lookup
with priority rules prevents ambiguity.

UNIQUENESS RULES:
- SKU/UPC/ALT_BARCODE: Globally unique (type + value)
- VENDOR_CODE: Unique per vendor (type + value + vendor_id)

SOFT DELETE: Deactivated identifiers are excluded from lookups but preserved
for audit history.
"""

from ..extensions import db
from ..models import ProductIdentifier, Product
from app.time_utils import utcnow


LOOKUP_PRIORITY = ["UPC", "SKU", "ALT_BARCODE", "VENDOR_CODE"]


def normalize_identifier(value: str) -> str:
    """Normalize to uppercase, no spaces."""
    return value.upper().strip().replace(" ", "")


def lookup_product(value: str, vendor_id: int | None = None) -> Product | None:
    """
    Lookup product by any identifier with deterministic priority.

    Priority: UPC > SKU > ALT_BARCODE > VENDOR_CODE
    Returns first match or None. Raises ValueError on ambiguity.

    IMPORTANT: Only active identifiers are considered in lookups.
    """
    normalized = normalize_identifier(value)

    # Only look up active identifiers
    q = db.session.query(ProductIdentifier).filter(
        ProductIdentifier.value == normalized,
        ProductIdentifier.is_active == True,
    )

    if vendor_id:
        q = q.filter(
            db.or_(
                ProductIdentifier.vendor_id == vendor_id,
                ProductIdentifier.vendor_id.is_(None)
            )
        )

    matches = q.all()

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0].product

    # Multiple matches - use priority
    for id_type in LOOKUP_PRIORITY:
        type_matches = [m for m in matches if m.type == id_type]
        if type_matches:
            if len(type_matches) > 1:
                # Include the type in the error message for clarity
                raise ValueError(
                    f"Ambiguous identifier: multiple {id_type} entries match value '{value}'. "
                    f"Found {len(type_matches)} matches. Please use a more specific identifier or provide vendor_id."
                )
            return type_matches[0].product

    return matches[0].product


def add_identifier(
    product_id: int,
    id_type: str,
    value: str,
    vendor_id: int | None = None,
    is_primary: bool = False
) -> ProductIdentifier:
    """
    Add identifier to product. Validates uniqueness.

    UNIQUENESS RULES:
    - For SKU/UPC/ALT_BARCODE: (type, value) must be unique
    - For VENDOR_CODE: (type, value, vendor_id) must be unique
      This allows different vendors to use the same code for different products.

    PRIMARY ENFORCEMENT:
    - If is_primary=True, all other identifiers for this product are set to is_primary=False
    - At most one primary identifier per product is allowed
    """
    normalized = normalize_identifier(value)

    # Check uniqueness based on type
    if id_type == "VENDOR_CODE":
        # VENDOR_CODE: unique within vendor scope
        existing = db.session.query(ProductIdentifier).filter_by(
            type=id_type,
            value=normalized,
            vendor_id=vendor_id,
            is_active=True,  # Only consider active identifiers for uniqueness
        ).first()

        if existing:
            if existing.product_id != product_id:
                raise ValueError(
                    f"VENDOR_CODE '{value}' already exists for vendor {vendor_id} on a different product"
                )
            return existing
    else:
        # SKU/UPC/ALT_BARCODE: globally unique
        existing = db.session.query(ProductIdentifier).filter_by(
            type=id_type,
            value=normalized,
            is_active=True,  # Only consider active identifiers for uniqueness
        ).first()

        if existing:
            if existing.product_id != product_id:
                raise ValueError(f"{id_type} '{value}' already exists for a different product")
            return existing

    # Enforce single primary per product
    if is_primary:
        # Set all existing identifiers for this product to non-primary
        db.session.query(ProductIdentifier).filter(
            ProductIdentifier.product_id == product_id,
            ProductIdentifier.is_primary == True,
        ).update({"is_primary": False})

    identifier = ProductIdentifier(
        product_id=product_id,
        type=id_type,
        value=normalized,
        vendor_id=vendor_id,
        is_primary=is_primary,
        is_active=True,
    )

    db.session.add(identifier)
    db.session.commit()
    return identifier


def deactivate_identifier(identifier_id: int) -> ProductIdentifier | None:
    """
    Deactivate an identifier (soft delete).

    Returns the deactivated identifier or None if not found.

    WHY: Soft delete preserves audit history while removing the identifier
    from lookups. Deactivated identifiers can be reactivated if needed.
    """
    identifier = db.session.query(ProductIdentifier).filter_by(id=identifier_id).first()

    if not identifier:
        return None

    if not identifier.is_active:
        raise ValueError("Identifier is already deactivated")

    identifier.is_active = False
    identifier.deactivated_at = utcnow()

    # If this was the primary identifier, we don't auto-promote another
    # The user should explicitly set a new primary if needed

    db.session.commit()
    return identifier


def reactivate_identifier(identifier_id: int) -> ProductIdentifier | None:
    """
    Reactivate a previously deactivated identifier.

    Returns the reactivated identifier or None if not found.
    Raises ValueError if reactivation would violate uniqueness constraints.
    """
    identifier = db.session.query(ProductIdentifier).filter_by(id=identifier_id).first()

    if not identifier:
        return None

    if identifier.is_active:
        raise ValueError("Identifier is already active")

    # Check if reactivation would violate uniqueness
    if identifier.type == "VENDOR_CODE":
        conflict = db.session.query(ProductIdentifier).filter(
            ProductIdentifier.type == identifier.type,
            ProductIdentifier.value == identifier.value,
            ProductIdentifier.vendor_id == identifier.vendor_id,
            ProductIdentifier.is_active == True,
            ProductIdentifier.id != identifier.id,
        ).first()
    else:
        conflict = db.session.query(ProductIdentifier).filter(
            ProductIdentifier.type == identifier.type,
            ProductIdentifier.value == identifier.value,
            ProductIdentifier.is_active == True,
            ProductIdentifier.id != identifier.id,
        ).first()

    if conflict:
        raise ValueError(
            f"Cannot reactivate: {identifier.type} '{identifier.value}' is already in use by another active identifier"
        )

    identifier.is_active = True
    identifier.deactivated_at = None

    db.session.commit()
    return identifier


def set_primary_identifier(identifier_id: int) -> ProductIdentifier | None:
    """
    Set an identifier as primary for its product.

    Removes primary status from all other identifiers for the same product.
    Returns the updated identifier or None if not found.
    """
    identifier = db.session.query(ProductIdentifier).filter_by(id=identifier_id).first()

    if not identifier:
        return None

    if not identifier.is_active:
        raise ValueError("Cannot set inactive identifier as primary")

    # Remove primary from all other identifiers for this product
    db.session.query(ProductIdentifier).filter(
        ProductIdentifier.product_id == identifier.product_id,
        ProductIdentifier.is_primary == True,
        ProductIdentifier.id != identifier.id,
    ).update({"is_primary": False})

    identifier.is_primary = True

    db.session.commit()
    return identifier


def get_product_identifiers(product_id: int, include_inactive: bool = False) -> list[ProductIdentifier]:
    """
    Get all identifiers for a product.

    Args:
        product_id: The product ID
        include_inactive: If True, include deactivated identifiers

    Returns list of ProductIdentifier objects.
    """
    q = db.session.query(ProductIdentifier).filter_by(product_id=product_id)

    if not include_inactive:
        q = q.filter(ProductIdentifier.is_active == True)

    return q.order_by(ProductIdentifier.type, ProductIdentifier.value).all()
