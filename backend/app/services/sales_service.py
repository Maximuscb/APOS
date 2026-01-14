"""
Phase 3: Sales Service - Document-first sale processing

WHY: Separates sale intent from inventory posting. Enables cart editing,
suspend/recall, and proper lifecycle.
"""

from ..extensions import db
from ..models import Sale, SaleLine, Product
from app.time_utils import utcnow
from .inventory_service import sell_inventory


def generate_document_number(store_id: int) -> str:
    """Generate next sale document number for store."""
    last_sale = db.session.query(Sale).filter_by(
        store_id=store_id
    ).order_by(Sale.id.desc()).first()

    if not last_sale:
        return f"S-{store_id:03d}-0001"

    # Extract number from last doc
    parts = last_sale.document_number.split("-")
    next_num = int(parts[-1]) + 1 if len(parts) > 0 else 1

    return f"S-{store_id:03d}-{next_num:04d}"


def create_sale(store_id: int, user_id: int | None = None) -> Sale:
    """Create new draft sale document."""
    doc_num = generate_document_number(store_id)

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
    sale = db.session.query(Sale).get(sale_id)
    if not sale:
        raise ValueError("Sale not found")

    if sale.status != "DRAFT":
        raise ValueError("Can only add lines to DRAFT sales")

    product = db.session.query(Product).get(product_id)
    if not product:
        raise ValueError("Product not found")

    if product.price_cents is None:
        raise ValueError("Product has no price")

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


def post_sale(sale_id: int) -> Sale:
    """
    Post sale - creates inventory transactions with lifecycle=POSTED.
    This is the bridge between sale document and inventory ledger.
    """
    sale = db.session.query(Sale).get(sale_id)
    if not sale:
        raise ValueError("Sale not found")

    if sale.status == "POSTED":
        return sale

    if sale.status != "DRAFT":
        raise ValueError(f"Cannot post sale with status {sale.status}")

    lines = db.session.query(SaleLine).filter_by(sale_id=sale_id).all()
    if not lines:
        raise ValueError("Cannot post sale with no lines")

    # Create inventory transactions for each line
    for i, line in enumerate(lines):
        inv_tx = sell_inventory(
            store_id=sale.store_id,
            product_id=line.product_id,
            quantity=line.quantity,
            sale_id=sale.document_number,
            sale_line_id=str(i + 1),
            status="POSTED",
            note=f"Sale {sale.document_number}"
        )
        line.inventory_transaction_id = inv_tx.id

    sale.status = "POSTED"
    sale.completed_at = utcnow()

    db.session.commit()
    return sale
