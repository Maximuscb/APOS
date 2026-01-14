"""
Phase 2: Identifier Service - First-class identifier lookup

WHY: Prevents silent mis-scans and barcode conflicts. Deterministic lookup
with priority rules prevents ambiguity.
"""

from ..extensions import db
from ..models import ProductIdentifier, Product


LOOKUP_PRIORITY = ["UPC", "SKU", "ALT_BARCODE", "VENDOR_CODE"]


def normalize_identifier(value: str) -> str:
    """Normalize to uppercase, no spaces."""
    return value.upper().strip().replace(" ", "")


def lookup_product(value: str, vendor_id: int | None = None) -> Product | None:
    """
    Lookup product by any identifier with deterministic priority.

    Priority: UPC > SKU > ALT_BARCODE > VENDOR_CODE
    Returns first match or None. Raises ValueError on ambiguity.
    """
    normalized = normalize_identifier(value)

    q = db.session.query(ProductIdentifier).filter(
        ProductIdentifier.value == normalized
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
                raise ValueError(f"Ambiguous identifier: multiple {id_type} match '{value}'")
            return type_matches[0].product

    return matches[0].product


def add_identifier(
    product_id: int,
    id_type: str,
    value: str,
    vendor_id: int | None = None,
    is_primary: bool = False
) -> ProductIdentifier:
    """Add identifier to product. Validates uniqueness."""
    normalized = normalize_identifier(value)

    # Check uniqueness
    existing = db.session.query(ProductIdentifier).filter_by(
        type=id_type,
        value=normalized
    ).first()

    if existing:
        if existing.product_id != product_id:
            raise ValueError(f"{id_type} '{value}' already exists for different product")
        return existing

    identifier = ProductIdentifier(
        product_id=product_id,
        type=id_type,
        value=normalized,
        vendor_id=vendor_id,
        is_primary=is_primary
    )

    db.session.add(identifier)
    db.session.commit()
    return identifier
