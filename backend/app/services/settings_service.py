from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
import sqlalchemy as sa

from ..extensions import db
from ..models import (
    OrganizationSetting,
    DeviceSetting,
    Organization,
    Register,
    Store,
    User,
    SettingRegistry,
    SettingValue,
    SettingAudit,
)
from . import permission_service
from ..settings_catalog import SETTINGS_CATALOG


SCOPE_ORG = "ORG"
SCOPE_STORE = "STORE"
SCOPE_DEVICE = "DEVICE"
SCOPE_USER = "USER"
ALL_SCOPES = {SCOPE_ORG, SCOPE_STORE, SCOPE_DEVICE, SCOPE_USER}
PRECEDENCE = [SCOPE_USER, SCOPE_DEVICE, SCOPE_STORE, SCOPE_ORG]

COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

STORE_ADMIN_ONLY_KEYS = {
    "store.timezone",
    "store.locale",
    "store.tax.tax_region_id",
    "store.tax.override_rates_json",
    "store.tax.prices_include_tax",
}


class SettingsError(ValueError):
    pass


class SettingsValidationError(SettingsError):
    pass


class SettingsAuthorizationError(SettingsError):
    pass


class SettingsNotFoundError(SettingsError):
    pass


@dataclass
class SettingsActor:
    user_id: int
    org_id: int | None
    store_id: int | None
    is_developer: bool
    permissions: set[str]


def make_actor(*, user_id: int) -> SettingsActor:
    user = db.session.query(User).filter_by(id=user_id).first()
    if not user:
        raise SettingsAuthorizationError("User not found")
    return SettingsActor(
        user_id=user.id,
        org_id=user.org_id,
        store_id=user.store_id,
        is_developer=bool(user.is_developer),
        permissions=permission_service.get_user_permissions(user.id),
    )


def _is_admin(actor: SettingsActor) -> bool:
    return actor.is_developer or ("SYSTEM_ADMIN" in actor.permissions)


def _has(actor: SettingsActor, code: str) -> bool:
    return _is_admin(actor) or code in actor.permissions


def _get_registry_map(include_developer: bool = False) -> dict[str, SettingRegistry]:
    ensure_registry_seeded()
    query = db.session.query(SettingRegistry)
    if not include_developer:
        query = query.filter(SettingRegistry.is_developer_only.is_(False))
    rows = query.order_by(SettingRegistry.key.asc()).all()
    return {r.key: r for r in rows}


def ensure_registry_seeded() -> int:
    existing = {
        r.key: r.id
        for r in db.session.query(SettingRegistry.key, SettingRegistry.id).all()
    }
    to_add = [row for row in SETTINGS_CATALOG if row["key"] not in existing]
    if not to_add:
        return 0
    for row in to_add:
        db.session.add(
            SettingRegistry(
                key=row["key"],
                scope_allowed=row["scope_allowed"],
                value_type=row["type"],
                default_value_json=row.get("default_value_json"),
                validation_json=row.get("validation_json") or {},
                description=row.get("description"),
                category=row["category"],
                subcategory=row.get("subcategory"),
                is_sensitive=bool(row.get("is_sensitive", False)),
                is_developer_only=bool(row.get("is_developer_only", False)),
                requires_restart=bool(row.get("requires_restart", False)),
                requires_reprice=bool(row.get("requires_reprice", False)),
                requires_recalc=bool(row.get("requires_recalc", False)),
                min_role_to_view=row.get("min_role_to_view"),
                min_role_to_edit=row.get("min_role_to_edit"),
            )
        )
    db.session.commit()
    return len(to_add)


def _scope_org_id(scope_type: str, scope_id: int) -> int:
    if scope_type == SCOPE_ORG:
        org = db.session.query(Organization).filter_by(id=scope_id).first()
        if not org:
            raise SettingsNotFoundError("Organization not found")
        return scope_id
    if scope_type == SCOPE_STORE:
        store = db.session.query(Store).filter_by(id=scope_id).first()
        if not store:
            raise SettingsNotFoundError("Store not found")
        return int(store.org_id)
    if scope_type == SCOPE_DEVICE:
        reg = db.session.query(Register).filter_by(id=scope_id).first()
        if not reg:
            raise SettingsNotFoundError("Device not found")
        return int(reg.org_id)
    if scope_type == SCOPE_USER:
        user = db.session.query(User).filter_by(id=scope_id).first()
        if not user:
            raise SettingsNotFoundError("User not found")
        if not user.org_id:
            raise SettingsNotFoundError("User has no organization")
        return int(user.org_id)
    raise SettingsValidationError("Invalid scope_type")


def _ensure_scope_in_org(scope_type: str, scope_id: int, org_id: int):
    resolved = _scope_org_id(scope_type, scope_id)
    if resolved != org_id:
        raise SettingsAuthorizationError("Cross-organization access denied")


def _can_view_scope(actor: SettingsActor, scope_type: str, scope_id: int) -> bool:
    if _is_admin(actor):
        return True
    if scope_type == SCOPE_ORG:
        return _has(actor, "VIEW_ORGANIZATION") and actor.org_id == scope_id
    if scope_type == SCOPE_STORE:
        if not _has(actor, "VIEW_STORES"):
            return False
        store = db.session.query(Store).filter_by(id=scope_id).first()
        if not store:
            return False
        if actor.org_id != store.org_id:
            return False
        return actor.store_id is None or actor.store_id == store.id
    if scope_type == SCOPE_DEVICE:
        if not _has(actor, "VIEW_DEVICE_SETTINGS"):
            return False
        device = db.session.query(Register).filter_by(id=scope_id).first()
        if not device:
            return False
        if actor.org_id != device.org_id:
            return False
        return actor.store_id is None or actor.store_id == device.store_id
    if scope_type == SCOPE_USER:
        if actor.user_id == scope_id:
            return True
        return _has(actor, "VIEW_USERS")
    return False


def _can_edit_scope(actor: SettingsActor, scope_type: str, scope_id: int, key: str) -> bool:
    if _is_admin(actor):
        return True
    if scope_type == SCOPE_ORG:
        return _has(actor, "MANAGE_ORGANIZATION") and actor.org_id == scope_id
    if scope_type == SCOPE_STORE:
        if key in STORE_ADMIN_ONLY_KEYS:
            return False
        if not _has(actor, "MANAGE_STORES"):
            return False
        store = db.session.query(Store).filter_by(id=scope_id).first()
        if not store:
            return False
        if actor.org_id != store.org_id:
            return False
        return actor.store_id is None or actor.store_id == store.id
    if scope_type == SCOPE_DEVICE:
        if not _has(actor, "MANAGE_DEVICE_SETTINGS"):
            return False
        device = db.session.query(Register).filter_by(id=scope_id).first()
        if not device:
            return False
        if actor.org_id != device.org_id:
            return False
        return actor.store_id is None or actor.store_id == device.store_id
    if scope_type == SCOPE_USER:
        if actor.user_id == scope_id:
            return True
        return _has(actor, "EDIT_USER")
    return False


def _coerce_value(registry: SettingRegistry, raw_value: Any) -> Any:
    t = registry.value_type
    v = raw_value
    if t == "bool":
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"true", "1", "yes", "on"}:
                return True
            if s in {"false", "0", "no", "off"}:
                return False
        raise SettingsValidationError(f"{registry.key}: expected boolean")
    if t in {"int", "decimal_cents", "duration_seconds"}:
        if isinstance(v, bool):
            raise SettingsValidationError(f"{registry.key}: expected integer")
        if isinstance(v, int):
            return v
        if isinstance(v, float) and int(v) == v:
            return int(v)
        if isinstance(v, str):
            try:
                return int(v.strip())
            except Exception:
                pass
        raise SettingsValidationError(f"{registry.key}: expected integer")
    if t == "decimal":
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v.strip())
            except Exception:
                pass
        raise SettingsValidationError(f"{registry.key}: expected decimal")
    if t in {"string", "enum"}:
        if v is None:
            return None
        if not isinstance(v, str):
            return str(v)
        return v
    if t == "json":
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return None
            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                try:
                    return json.loads(s)
                except Exception:
                    pass
        return v
    if t == "color":
        if not isinstance(v, str) or not COLOR_RE.match(v.strip()):
            raise SettingsValidationError(f"{registry.key}: expected hex color")
        return v.strip()
    return v


def _validate_constraints(registry: SettingRegistry, value: Any):
    validation = registry.validation_json or {}
    if value is None:
        return
    if registry.value_type == "enum":
        options = validation.get("enum", [])
        if options and value not in options:
            raise SettingsValidationError(f"{registry.key}: expected one of {options}")
    if registry.value_type in {"int", "decimal", "decimal_cents", "duration_seconds"}:
        if "min" in validation and value < validation["min"]:
            raise SettingsValidationError(f"{registry.key}: must be >= {validation['min']}")
        if "max" in validation and value > validation["max"]:
            raise SettingsValidationError(f"{registry.key}: must be <= {validation['max']}")
    if registry.value_type == "string" and "regex" in validation:
        if not re.match(validation["regex"], str(value)):
            raise SettingsValidationError(f"{registry.key}: format is invalid")


def _normalize_value(registry: SettingRegistry, value: Any) -> Any:
    coerced = _coerce_value(registry, value)
    _validate_constraints(registry, coerced)
    return coerced


def list_registry(actor: SettingsActor) -> list[dict]:
    query = db.session.query(SettingRegistry)
    if not actor.is_developer:
        query = query.filter(SettingRegistry.is_developer_only.is_(False))
    rows = query.order_by(SettingRegistry.category.asc(), SettingRegistry.subcategory.asc(), SettingRegistry.key.asc()).all()
    return [r.to_dict() for r in rows]


def _load_scope_values(scope_filters: list[tuple[str, int]]) -> dict[tuple[str, int], dict[str, Any]]:
    if not scope_filters:
        return {}
    clauses = []
    for scope_type, scope_id in scope_filters:
        clauses.append(sa.and_(SettingValue.scope_type == scope_type, SettingValue.scope_id == scope_id))
    rows = db.session.query(SettingValue).filter(sa.or_(*clauses)).all()
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        out.setdefault((row.scope_type, row.scope_id), {})[row.key] = row.value_json
    return out


def resolve_effective_settings(
    *,
    org_id: int,
    store_id: int | None = None,
    device_id: int | None = None,
    user_id: int | None = None,
    include_sensitive: bool = False,
    include_developer: bool = False,
) -> dict[str, dict[str, Any]]:
    registry_map = _get_registry_map(include_developer=include_developer)
    scope_filters: list[tuple[str, int]] = [(SCOPE_ORG, org_id)]
    if store_id:
        scope_filters.append((SCOPE_STORE, store_id))
    if device_id:
        scope_filters.append((SCOPE_DEVICE, device_id))
    if user_id:
        scope_filters.append((SCOPE_USER, user_id))
    values_by_scope = _load_scope_values(scope_filters)

    result: dict[str, dict[str, Any]] = {}
    for key, reg in registry_map.items():
        if reg.is_sensitive and not include_sensitive:
            continue
        allowed = set(reg.scope_allowed or [])
        chosen_value = reg.default_value_json
        chosen_source = "SYSTEM_DEFAULT"
        for scope in PRECEDENCE:
            scope_id = None
            if scope == SCOPE_USER:
                scope_id = user_id
            elif scope == SCOPE_DEVICE:
                scope_id = device_id
            elif scope == SCOPE_STORE:
                scope_id = store_id
            elif scope == SCOPE_ORG:
                scope_id = org_id
            if scope_id is None:
                continue
            if scope not in allowed:
                continue
            scoped = values_by_scope.get((scope, scope_id), {})
            if key in scoped:
                chosen_value = scoped[key]
                chosen_source = scope
                break
        result[key] = {
            "value": chosen_value,
            "source": chosen_source,
            "type": reg.value_type,
            "category": reg.category,
            "subcategory": reg.subcategory,
            "requires_restart": bool(reg.requires_restart),
            "requires_reprice": bool(reg.requires_reprice),
            "requires_recalc": bool(reg.requires_recalc),
        }
    return result


def get_scope_settings(
    *,
    actor: SettingsActor,
    scope_type: str,
    scope_id: int,
) -> dict[str, Any]:
    if scope_type not in ALL_SCOPES:
        raise SettingsValidationError("Invalid scope_type")
    if not _can_view_scope(actor, scope_type, scope_id):
        raise SettingsAuthorizationError("Access denied")
    org_id = _scope_org_id(scope_type, scope_id)
    _ensure_scope_in_org(scope_type, scope_id, org_id)

    registry_map = _get_registry_map(include_developer=actor.is_developer)
    effective = resolve_effective_settings(
        org_id=org_id,
        store_id=scope_id if scope_type == SCOPE_STORE else None,
        device_id=scope_id if scope_type == SCOPE_DEVICE else None,
        user_id=scope_id if scope_type == SCOPE_USER else None,
        include_sensitive=False,
        include_developer=actor.is_developer,
    )
    local_rows = db.session.query(SettingValue).filter_by(scope_type=scope_type, scope_id=scope_id).all()
    local_map = {r.key: r for r in local_rows}

    items = []
    for key, reg in registry_map.items():
        allowed = set(reg.scope_allowed or [])
        if scope_type not in allowed:
            continue
        if reg.is_sensitive:
            continue
        local = local_map.get(key)
        eff = effective.get(key, {"value": reg.default_value_json, "source": "SYSTEM_DEFAULT"})
        items.append(
            {
                "key": key,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "value_json": local.value_json if local else None,
                "effective_value_json": eff["value"],
                "effective_source": eff["source"],
                "inherited": local is None,
                "registry": reg.to_dict(),
            }
        )
    items.sort(key=lambda x: x["key"])
    return {"scope_type": scope_type, "scope_id": scope_id, "org_id": org_id, "items": items}


def _write_audit(
    *,
    key: str,
    scope_type: str,
    scope_id: int,
    old_value: Any,
    new_value: Any,
    changed_by_user_id: int,
    change_reason: str | None = None,
    request_metadata_json: dict[str, Any] | None = None,
):
    db.session.add(
        SettingAudit(
            key=key,
            scope_type=scope_type,
            scope_id=scope_id,
            old_value_json=old_value,
            new_value_json=new_value,
            changed_by_user_id=changed_by_user_id,
            change_reason=change_reason,
            request_metadata_json=request_metadata_json,
        )
    )


def bulk_upsert_scope_settings(
    *,
    actor: SettingsActor,
    scope_type: str,
    scope_id: int,
    updates: list[dict[str, Any]],
    source: str = "UI",
    change_reason: str | None = None,
    request_metadata_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if scope_type not in ALL_SCOPES:
        raise SettingsValidationError("Invalid scope_type")
    if not updates:
        return {"updated": [], "errors": []}
    org_id = _scope_org_id(scope_type, scope_id)
    _ensure_scope_in_org(scope_type, scope_id, org_id)
    if actor.org_id != org_id and not actor.is_developer:
        raise SettingsAuthorizationError("Access denied")

    registry_map = _get_registry_map(include_developer=actor.is_developer)
    updated: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for item in updates:
        key = item.get("key")
        unset = bool(item.get("unset"))
        if not key or key not in registry_map:
            errors.append({"key": key, "error": "Unknown setting key"})
            continue
        reg = registry_map[key]
        if reg.is_developer_only and not actor.is_developer:
            errors.append({"key": key, "error": "Developer-only setting"})
            continue
        allowed = set(reg.scope_allowed or [])
        if scope_type not in allowed:
            errors.append({"key": key, "error": f"Scope {scope_type} is not allowed for this key"})
            continue
        if not _can_edit_scope(actor, scope_type, scope_id, key):
            errors.append({"key": key, "error": "Access denied"})
            continue
        try:
            row = db.session.query(SettingValue).filter_by(scope_type=scope_type, scope_id=scope_id, key=key).first()
            old_value = row.value_json if row else None
            if unset:
                if row:
                    db.session.delete(row)
                _write_audit(
                    key=key,
                    scope_type=scope_type,
                    scope_id=scope_id,
                    old_value=old_value,
                    new_value=None,
                    changed_by_user_id=actor.user_id,
                    change_reason=change_reason,
                    request_metadata_json=request_metadata_json,
                )
                updated.append({"key": key, "scope_type": scope_type, "scope_id": scope_id, "value_json": None, "unset": True})
                continue

            normalized = _normalize_value(reg, item.get("value_json"))
            if row:
                row.value_json = normalized
                row.updated_by_user_id = actor.user_id
                row.source = source
            else:
                row = SettingValue(
                    key=key,
                    scope_type=scope_type,
                    scope_id=scope_id,
                    value_json=normalized,
                    updated_by_user_id=actor.user_id,
                    source=source,
                )
                db.session.add(row)
            _write_audit(
                key=key,
                scope_type=scope_type,
                scope_id=scope_id,
                old_value=old_value,
                new_value=normalized,
                changed_by_user_id=actor.user_id,
                change_reason=change_reason,
                request_metadata_json=request_metadata_json,
            )
            updated.append({"key": key, "scope_type": scope_type, "scope_id": scope_id, "value_json": normalized, "unset": False})
        except SettingsError as exc:
            errors.append({"key": key, "error": str(exc)})

    if errors:
        db.session.rollback()
        return {"updated": [], "errors": errors}

    db.session.commit()
    return {"updated": updated, "errors": []}


# -----------------------------------------------------------------------------
# Legacy compatibility wrappers (existing endpoints)
# -----------------------------------------------------------------------------

def get_org_settings(org_id: int) -> list[dict]:
    rows = db.session.query(OrganizationSetting).filter_by(org_id=org_id).order_by(OrganizationSetting.key).all()
    return [r.to_dict() for r in rows]


def upsert_org_setting(org_id: int, key: str, value: str | None, user_id: int) -> dict:
    row = db.session.query(OrganizationSetting).filter_by(org_id=org_id, key=key).first()
    if row:
        row.value = value
        row.updated_by_user_id = user_id
    else:
        row = OrganizationSetting(org_id=org_id, key=key, value=value, updated_by_user_id=user_id)
        db.session.add(row)
    db.session.commit()
    return row.to_dict()


def _require_device_in_org(device_id: int, org_id: int) -> Register:
    device = db.session.query(Register).filter_by(id=device_id, org_id=org_id).first()
    if not device:
        raise SettingsNotFoundError("Device not found")
    return device


def get_device_settings(device_id: int, org_id: int) -> list[dict]:
    _require_device_in_org(device_id, org_id)
    rows = db.session.query(DeviceSetting).filter_by(device_id=device_id).order_by(DeviceSetting.key).all()
    return [r.to_dict() for r in rows]


def upsert_device_setting(device_id: int, org_id: int, key: str, value: str | None, user_id: int) -> dict:
    _require_device_in_org(device_id, org_id)
    row = db.session.query(DeviceSetting).filter_by(device_id=device_id, key=key).first()
    if row:
        row.value = value
        row.updated_by_user_id = user_id
    else:
        row = DeviceSetting(device_id=device_id, key=key, value=value, updated_by_user_id=user_id)
        db.session.add(row)
    db.session.commit()
    return row.to_dict()
