from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..extensions import db
from ..models import (
    InventoryTransaction,
    Product,
    ProductIdentifier,
    Sale,
    SaleLine,
    Store,
    User,
)
from app.time_utils import parse_iso_datetime, utcnow
from .document_service import next_document_number
from .inventory_service import get_quantity_on_hand


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    return int(float(text))


def _to_cents(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value * 100))
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text:
        return None
    return int(round(float(text) * 100))


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


@dataclass
class SchemaContext:
    batch_id: int
    org_id: int
    actor_user_id: int
    staging_row_number: int
    source_foreign_id: str | None


class BaseImportSchema:
    def normalize_row(self, raw_row: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def validate_row(self, normalized_row: dict[str, Any]) -> list[str]:
        raise NotImplementedError

    def auto_resolve_references(self, normalized_row: dict[str, Any], org_id: int) -> list[dict[str, Any]]:
        raise NotImplementedError

    def post_row(self, normalized_row: dict[str, Any], context: SchemaContext) -> dict[str, Any]:
        raise NotImplementedError


class ProductsSchema(BaseImportSchema):
    def normalize_row(self, raw_row: dict[str, Any]) -> dict[str, Any]:
        identifiers = raw_row.get("identifiers")
        if identifiers is None:
            identifiers = []
        elif isinstance(identifiers, dict):
            identifiers = [identifiers]
        elif not isinstance(identifiers, list):
            identifiers = []

        id_type = _to_text(raw_row.get("identifier_type"))
        id_value = _to_text(raw_row.get("identifier_value"))
        if id_type and id_value:
            identifiers.append({"type": id_type, "value": id_value, "is_primary": True})

        return {
            "store_id": _to_int(raw_row.get("store_id")),
            "sku": _to_text(raw_row.get("sku")) or _to_text(raw_row.get("product_sku")),
            "name": _to_text(raw_row.get("name")) or _to_text(raw_row.get("product_name")),
            "description": _to_text(raw_row.get("description")),
            "price_cents": _to_int(raw_row.get("price_cents")) if raw_row.get("price_cents") not in (None, "") else _to_cents(raw_row.get("price")),
            "is_active": bool(raw_row.get("is_active", True)),
            "identifiers": identifiers,
        }

    def validate_row(self, normalized_row: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not normalized_row.get("store_id"):
            errors.append("store_id is required")
        if not normalized_row.get("sku"):
            errors.append("sku is required")
        if not normalized_row.get("name"):
            errors.append("name is required")
        return errors

    def auto_resolve_references(self, normalized_row: dict[str, Any], org_id: int) -> list[dict[str, Any]]:
        unmapped: list[dict[str, Any]] = []
        store_id = normalized_row.get("store_id")
        if store_id:
            store = db.session.query(Store).filter_by(id=store_id, org_id=org_id).first()
            if not store:
                unmapped.append({"field": "store_id", "value": store_id, "entity_type": "STORE"})
        return unmapped

    def post_row(self, normalized_row: dict[str, Any], context: SchemaContext) -> dict[str, Any]:
        store_id = normalized_row["store_id"]
        sku = normalized_row["sku"]
        product = db.session.query(Product).filter_by(store_id=store_id, sku=sku).first()
        created = product is None
        if created:
            product = Product(
                store_id=store_id,
                sku=sku,
                name=normalized_row["name"],
                description=normalized_row.get("description"),
                price_cents=normalized_row.get("price_cents"),
                is_active=normalized_row.get("is_active", True),
                imported_from_batch_id=context.batch_id,
            )
            db.session.add(product)
            db.session.flush()
        else:
            product.name = normalized_row["name"]
            product.description = normalized_row.get("description")
            product.price_cents = normalized_row.get("price_cents")
            product.is_active = normalized_row.get("is_active", True)
            product.imported_from_batch_id = context.batch_id
            db.session.flush()

        store = db.session.query(Store).filter_by(id=store_id).first()
        for identifier in normalized_row.get("identifiers", []):
            id_type = _to_text(identifier.get("type"))
            id_value = _to_text(identifier.get("value"))
            if not id_type or not id_value:
                continue
            existing = db.session.query(ProductIdentifier).filter_by(
                org_id=store.org_id,
                type=id_type.upper(),
                value=id_value.upper(),
            ).first()
            if existing:
                existing.product_id = product.id
                existing.store_id = store_id
                existing.is_active = True
                existing.vendor_id = _to_int(identifier.get("vendor_id"))
                existing.is_primary = bool(identifier.get("is_primary", False))
            else:
                db.session.add(
                    ProductIdentifier(
                        product_id=product.id,
                        org_id=store.org_id,
                        store_id=store_id,
                        type=id_type.upper(),
                        value=id_value.upper(),
                        vendor_id=_to_int(identifier.get("vendor_id")),
                        is_primary=bool(identifier.get("is_primary", False)),
                        is_active=True,
                    )
                )

        return {
            "entity_type": "product",
            "entity_id": product.id,
            "event_type": "PRODUCT_CREATED" if created else "PRODUCT_UPDATED",
            "event_category": "inventory",
            "store_id": store_id,
            "occurred_at": utcnow(),
        }


class InventorySchema(BaseImportSchema):
    def normalize_row(self, raw_row: dict[str, Any]) -> dict[str, Any]:
        return {
            "store_id": _to_int(raw_row.get("store_id")),
            "product_id": _to_int(raw_row.get("product_id")),
            "sku": _to_text(raw_row.get("sku")) or _to_text(raw_row.get("product_sku")),
            "identifier_value": _to_text(raw_row.get("identifier_value")) or _to_text(raw_row.get("barcode")),
            "quantity_delta": _to_int(raw_row.get("quantity_delta")),
            "unit_cost_cents": _to_int(raw_row.get("unit_cost_cents")) if raw_row.get("unit_cost_cents") not in (None, "") else _to_cents(raw_row.get("unit_cost")),
            "note": _to_text(raw_row.get("note")),
            "occurred_at": _to_text(raw_row.get("occurred_at")),
        }

    def validate_row(self, normalized_row: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not normalized_row.get("store_id"):
            errors.append("store_id is required")
        if normalized_row.get("quantity_delta") is None:
            errors.append("quantity_delta is required")
        if not (
            normalized_row.get("product_id")
            or normalized_row.get("sku")
            or normalized_row.get("identifier_value")
        ):
            errors.append("product_id, sku, or identifier_value is required")
        return errors

    def auto_resolve_references(self, normalized_row: dict[str, Any], org_id: int) -> list[dict[str, Any]]:
        unmapped: list[dict[str, Any]] = []
        store_id = normalized_row.get("store_id")
        store = db.session.query(Store).filter_by(id=store_id, org_id=org_id).first()
        if not store:
            return [{"field": "store_id", "value": store_id, "entity_type": "STORE"}]

        product = None
        if normalized_row.get("product_id"):
            product = db.session.query(Product).filter_by(
                id=normalized_row["product_id"],
                store_id=store_id,
            ).first()
        if not product and normalized_row.get("sku"):
            product = db.session.query(Product).filter_by(
                store_id=store_id,
                sku=normalized_row["sku"],
            ).first()
        if not product and normalized_row.get("identifier_value"):
            ident = db.session.query(ProductIdentifier).filter_by(
                org_id=org_id,
                value=normalized_row["identifier_value"].upper(),
                is_active=True,
            ).first()
            if ident:
                product = db.session.query(Product).filter_by(id=ident.product_id).first()

        if not product:
            unmapped.append(
                {
                    "field": "product",
                    "value": normalized_row.get("product_id") or normalized_row.get("sku") or normalized_row.get("identifier_value"),
                    "entity_type": "PRODUCT",
                }
            )
        else:
            normalized_row["resolved_product_id"] = product.id
        return unmapped

    def post_row(self, normalized_row: dict[str, Any], context: SchemaContext) -> dict[str, Any]:
        occurred_at = parse_iso_datetime(normalized_row.get("occurred_at")) or utcnow()
        tx = InventoryTransaction(
            store_id=normalized_row["store_id"],
            product_id=normalized_row["resolved_product_id"],
            type="IMPORT_ADJUSTMENT",
            quantity_delta=normalized_row["quantity_delta"],
            unit_cost_cents=normalized_row.get("unit_cost_cents"),
            note=normalized_row.get("note"),
            occurred_at=occurred_at,
            status="POSTED",
            posted_by_user_id=context.actor_user_id,
            posted_at=utcnow(),
        )
        db.session.add(tx)
        db.session.flush()
        return {
            "entity_type": "inventory_transaction",
            "entity_id": tx.id,
            "event_type": "INVENTORY_ADJUSTMENT",
            "event_category": "inventory",
            "store_id": normalized_row["store_id"],
            "occurred_at": occurred_at,
        }


class SalesSchema(BaseImportSchema):
    def normalize_row(self, raw_row: dict[str, Any]) -> dict[str, Any]:
        lines = raw_row.get("lines") or raw_row.get("line_items") or []
        if not isinstance(lines, list):
            lines = []
        if not lines:
            single = {
                "product_id": raw_row.get("product_id"),
                "sku": raw_row.get("sku") or raw_row.get("product_sku"),
                "identifier_value": raw_row.get("identifier_value") or raw_row.get("barcode"),
                "quantity": raw_row.get("quantity"),
                "unit_price_cents": raw_row.get("unit_price_cents"),
                "unit_price": raw_row.get("unit_price") or raw_row.get("price"),
                "discount_cents": raw_row.get("discount_cents"),
                "discount_reason": raw_row.get("discount_reason"),
                "tax_cents": raw_row.get("tax_cents"),
            }
            if single["product_id"] or single["sku"] or single["identifier_value"]:
                lines = [single]

        normalized_lines: list[dict[str, Any]] = []
        for line in lines:
            normalized_lines.append(
                {
                    "product_id": _to_int(line.get("product_id")),
                    "sku": _to_text(line.get("sku")) or _to_text(line.get("product_sku")),
                    "identifier_value": _to_text(line.get("identifier_value")) or _to_text(line.get("barcode")),
                    "quantity": _to_int(line.get("quantity")) or 1,
                    "unit_price_cents": _to_int(line.get("unit_price_cents")) if line.get("unit_price_cents") not in (None, "") else _to_cents(line.get("unit_price") or line.get("price")),
                    "discount_cents": _to_int(line.get("discount_cents")),
                    "discount_reason": _to_text(line.get("discount_reason")),
                    "tax_cents": _to_int(line.get("tax_cents")),
                }
            )

        return {
            "store_id": _to_int(raw_row.get("store_id")),
            "occurred_at": _to_text(raw_row.get("occurred_at")),
            "document_number": _to_text(raw_row.get("document_number")),
            "created_by_user_id": _to_int(raw_row.get("created_by_user_id") or raw_row.get("user_id")),
            "register_id": _to_int(raw_row.get("register_id")),
            "register_session_id": _to_int(raw_row.get("register_session_id")),
            "customer_id": _to_int(raw_row.get("customer_id")),
            "tax_cents": _to_int(raw_row.get("tax_cents")) or 0,
            "lines": normalized_lines,
        }

    def validate_row(self, normalized_row: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not normalized_row.get("store_id"):
            errors.append("store_id is required")
        lines = normalized_row.get("lines") or []
        if not lines:
            errors.append("at least one sale line is required")
            return errors
        for idx, line in enumerate(lines, start=1):
            if (line.get("quantity") or 0) <= 0:
                errors.append(f"line {idx}: quantity must be > 0")
            if not (line.get("product_id") or line.get("sku") or line.get("identifier_value")):
                errors.append(f"line {idx}: product reference required")
        return errors

    def auto_resolve_references(self, normalized_row: dict[str, Any], org_id: int) -> list[dict[str, Any]]:
        unmapped: list[dict[str, Any]] = []
        store_id = normalized_row.get("store_id")
        store = db.session.query(Store).filter_by(id=store_id, org_id=org_id).first()
        if not store:
            return [{"field": "store_id", "value": store_id, "entity_type": "STORE"}]

        user_id = normalized_row.get("created_by_user_id")
        if user_id:
            user = db.session.query(User).filter_by(id=user_id, org_id=org_id).first()
            if not user:
                unmapped.append({"field": "created_by_user_id", "value": user_id, "entity_type": "USER"})

        for idx, line in enumerate(normalized_row.get("lines", []), start=1):
            product = None
            if line.get("product_id"):
                product = db.session.query(Product).filter_by(id=line["product_id"], store_id=store_id).first()
            if not product and line.get("sku"):
                product = db.session.query(Product).filter_by(store_id=store_id, sku=line["sku"]).first()
            if not product and line.get("identifier_value"):
                ident = db.session.query(ProductIdentifier).filter_by(
                    org_id=org_id,
                    value=line["identifier_value"].upper(),
                    is_active=True,
                ).first()
                if ident:
                    product = db.session.query(Product).filter_by(id=ident.product_id).first()

            if not product:
                unmapped.append(
                    {
                        "field": f"lines[{idx}].product",
                        "value": line.get("product_id") or line.get("sku") or line.get("identifier_value"),
                        "entity_type": "PRODUCT",
                    }
                )
            else:
                line["resolved_product_id"] = product.id
                if line.get("unit_price_cents") is None:
                    line["unit_price_cents"] = product.price_cents or 0
        return unmapped

    def post_row(self, normalized_row: dict[str, Any], context: SchemaContext) -> dict[str, Any]:
        occurred_at = parse_iso_datetime(normalized_row.get("occurred_at")) or utcnow()
        store_id = normalized_row["store_id"]
        lines = normalized_row["lines"]

        requested_by_product: dict[int, int] = {}
        for line in lines:
            product_id = line["resolved_product_id"]
            requested_by_product[product_id] = requested_by_product.get(product_id, 0) + int(line["quantity"])
        for product_id, needed in requested_by_product.items():
            on_hand = get_quantity_on_hand(store_id, product_id)
            if on_hand < needed:
                raise ValueError(
                    f"inventory would go negative for product {product_id}: on_hand={on_hand}, requested={needed}"
                )

        document_number = normalized_row.get("document_number") or next_document_number(
            store_id=store_id, document_type="SALE", prefix="S"
        )
        created_by_user_id = normalized_row.get("created_by_user_id") or context.actor_user_id
        total_due = 0
        total_tax = int(normalized_row.get("tax_cents") or 0)

        sale = Sale(
            store_id=store_id,
            document_number=document_number,
            status="POSTED",
            created_by_user_id=created_by_user_id,
            register_id=normalized_row.get("register_id"),
            register_session_id=normalized_row.get("register_session_id"),
            completed_at=occurred_at,
            imported_from_batch_id=context.batch_id,
            tax_cents=total_tax,
            customer_id=normalized_row.get("customer_id"),
            payment_status="UNPAID",
        )
        db.session.add(sale)
        db.session.flush()

        for idx, line in enumerate(lines, start=1):
            unit_price_cents = int(line.get("unit_price_cents") or 0)
            quantity = int(line["quantity"])
            line_total = unit_price_cents * quantity
            total_due += line_total

            sale_line = SaleLine(
                sale_id=sale.id,
                product_id=line["resolved_product_id"],
                quantity=quantity,
                unit_price_cents=unit_price_cents,
                line_total_cents=line_total,
                original_price_cents=unit_price_cents,
                discount_cents=_to_int(line.get("discount_cents")) or 0,
                discount_reason=_to_text(line.get("discount_reason")),
                tax_cents=_to_int(line.get("tax_cents")) or 0,
            )
            db.session.add(sale_line)
            db.session.flush()

            inv_tx = InventoryTransaction(
                store_id=store_id,
                product_id=line["resolved_product_id"],
                type="SALE",
                quantity_delta=-quantity,
                note=f"Imported sale {document_number}",
                occurred_at=occurred_at,
                sale_id=document_number,
                sale_line_id=str(idx),
                status="POSTED",
                posted_by_user_id=created_by_user_id,
                posted_at=utcnow(),
            )
            db.session.add(inv_tx)
            db.session.flush()
            sale_line.inventory_transaction_id = inv_tx.id

        sale.total_due_cents = total_due
        sale.total_paid_cents = 0
        sale.change_due_cents = 0
        db.session.flush()

        return {
            "entity_type": "sale",
            "entity_id": sale.id,
            "event_type": "SALE_POSTED",
            "event_category": "sales",
            "store_id": store_id,
            "occurred_at": occurred_at,
            "sale_id": sale.id,
        }


SCHEMAS: dict[str, BaseImportSchema] = {
    "Products": ProductsSchema(),
    "Inventory": InventorySchema(),
    "Sales": SalesSchema(),
}
