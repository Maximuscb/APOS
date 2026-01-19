from __future__ import annotations
from datetime import datetime
from app.time_utils import parse_iso_datetime

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Boolean, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeMeta


# Maximum price: $9,999,999.99 (999,999,999 cents)
# This prevents database overflow issues and nonsensical prices
MAX_PRICE_CENTS = 999_999_999


class ValidationError(ValueError):
    """400-level input problem."""


class ConflictError(ValueError):
    """409-level business rule conflict (e.g., duplicate SKU)."""


@dataclass(frozen=True)
class ModelValidationPolicy:
    """
    Central policy layer:
    - writable_fields: what clients are allowed to set (security boundary)
    - required_on_create: fields required for POST
    - allow_null_fields: extra allowlist for setting null even if you want to special-case later
    """
    writable_fields: set[str]
    required_on_create: set[str] = None  # type: ignore
    # Optional: keep for future; currently we just honor SQLAlchemy column.nullable
    allow_null_fields: set[str] | None = None


def _columns_by_key(model: DeclarativeMeta) -> dict[str, Any]:
    mapper = model.__mapper__
    return {c.key: c for c in mapper.columns}


def _coerce_value(col, value: Any):
    coltype = col.type

    if value is None:
        return None

    # Integers - strict validation to reject floats and scientific notation
    if isinstance(coltype, Integer):
        # Already an int (but not bool which is a subclass of int)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        # String input - must be plain digits (with optional leading minus)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValidationError(f"{col.key} must be an integer")
            # Reject scientific notation (e.g., "1e15", "1E10")
            if 'e' in stripped.lower():
                raise ValidationError(f"{col.key} must be a plain integer (scientific notation not allowed)")
            # Reject decimal points (e.g., "12.5")
            if '.' in stripped:
                raise ValidationError(f"{col.key} must be an integer (no decimals)")
            try:
                return int(stripped)
            except ValueError:
                raise ValidationError(f"{col.key} must be an integer")
        # Reject floats explicitly
        if isinstance(value, float):
            raise ValidationError(f"{col.key} must be an integer, not a decimal")
        # Other types
        raise ValidationError(f"{col.key} must be an integer")

    # Booleans
    if isinstance(coltype, Boolean):
        if isinstance(value, bool):
            return value
        # fallback: truthiness
        return bool(value)

    # Datetimes (accept ISO-8601 strings; normalize to UTC)
    if isinstance(coltype, DateTime):
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                dt = parse_iso_datetime(value)
            except Exception:
                raise ValidationError(f"{col.key} must be an ISO-8601 datetime")
            if dt is None:
                raise ValidationError(f"{col.key} must be an ISO-8601 datetime")
            return dt
        raise ValidationError(f"{col.key} must be a datetime")


    # Strings / Text
    if isinstance(coltype, (String, Text)):
        return str(value).strip()

    # Default: leave as-is
    return value


def validate_payload(
    *,
    model: DeclarativeMeta,
    payload: dict,
    policy: ModelValidationPolicy,
    partial: bool,
) -> dict:
    """
    Validates + normalizes incoming JSON against:
    - SQLAlchemy column metadata (nullable, type, String length)
    - a policy allowlist (writable_fields)
    - required_on_create (if partial=False)
    Returns a cleaned patch dict with only writable fields.

    partial=False: create semantics (enforce required_on_create)
    partial=True: patch semantics (validate only provided keys)
    """
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValidationError("Invalid JSON payload")

    required = policy.required_on_create or set()
    if not partial:
        missing = [f for f in required if f not in payload]
        if missing:
            raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    cols = _columns_by_key(model)

    # Reject unknown / non-writable fields
    for k in payload.keys():
        if k not in policy.writable_fields:
            raise ValidationError(f"Field not allowed: {k}")
        if k not in cols:
            raise ValidationError(f"Unknown field: {k}")

    patch: dict = {}

    for k, raw in payload.items():
        col = cols[k]

        # NULL handling
        if raw is None:
            if not col.nullable:
                raise ValidationError(f"{k} cannot be null")
            patch[k] = None
            continue

        val = _coerce_value(col, raw)

        # Blank string check for non-nullable text fields
        if isinstance(col.type, (String, Text)) and not col.nullable:
            if isinstance(val, str) and val == "":
                raise ValidationError(f"{k} cannot be blank")

        # Max length check for String(n)
        if isinstance(col.type, String) and col.type.length and isinstance(val, str):
            if len(val) > col.type.length:
                raise ValidationError(f"{k} exceeds max length {col.type.length}")

        patch[k] = val

    return patch


def enforce_rules_product(patch: dict) -> None:
    """
    Business rules that are not captured by SQLAlchemy metadata alone.
    Keep these small and centralized.
    """
    if "price_cents" in patch and patch["price_cents"] is not None:
        price = patch["price_cents"]
        # Type check (should already be int from _coerce_value, but be defensive)
        if not isinstance(price, int):
            raise ValidationError("price_cents must be an integer")
        # Range checks
        if price < 0:
            raise ValidationError("price_cents must be >= 0")
        if price > MAX_PRICE_CENTS:
            raise ValidationError(f"price_cents cannot exceed {MAX_PRICE_CENTS} (${MAX_PRICE_CENTS / 100:,.2f})")

def enforce_rules_inventory_receive(patch: dict) -> None:
    # RECEIVE requires qty > 0 and unit_cost_cents present and >= 0
    if "quantity_delta" in patch:
        if patch["quantity_delta"] is None or patch["quantity_delta"] <= 0:
            raise ValidationError("quantity_delta must be > 0 for RECEIVE")

    if "unit_cost_cents" not in patch or patch["unit_cost_cents"] is None:
        raise ValidationError("unit_cost_cents is required for RECEIVE")

    if patch["unit_cost_cents"] < 0:
        raise ValidationError("unit_cost_cents must be >= 0")


def enforce_rules_inventory_adjust(patch: dict) -> None:
    # ADJUST requires qty != 0 and forbids unit_cost_cents
    if "quantity_delta" in patch:
        if patch["quantity_delta"] is None or patch["quantity_delta"] == 0:
            raise ValidationError("quantity_delta must be non-zero for ADJUST")

    if "unit_cost_cents" in patch and patch["unit_cost_cents"] is not None:
        raise ValidationError("unit_cost_cents must be omitted for ADJUST")

def enforce_rules_inventory_sale(patch: dict) -> None:
    # SALE requires qty > 0, forbids unit_cost_cents, and requires sale identifiers
    if "quantity_delta" not in patch:
        raise ValidationError("quantity_delta is required for SALE")

    if patch["quantity_delta"] is None or patch["quantity_delta"] <= 0:
        raise ValidationError("quantity_delta must be > 0 for SALE")

    # SALE never accepts unit_cost_cents input (backend computes WAC snapshot)
    if "unit_cost_cents" in patch and patch["unit_cost_cents"] is not None:
        raise ValidationError("unit_cost_cents must be omitted for SALE")

    sale_id = patch.get("sale_id")
    if sale_id is None or str(sale_id).strip() == "":
        raise ValidationError("sale_id is required for SALE")

    sale_line_id = patch.get("sale_line_id")
    if sale_line_id is None or str(sale_line_id).strip() == "":
        raise ValidationError("sale_line_id is required for SALE")
