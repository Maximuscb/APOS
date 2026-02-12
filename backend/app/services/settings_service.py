from __future__ import annotations

import json

from ..extensions import db
from ..models import OrganizationSetting, DeviceSetting, Register
from .ledger_service import append_ledger_event


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
        raise ValueError("Device not found")
    return device


def get_device_settings(device_id: int, org_id: int) -> list[dict]:
    _require_device_in_org(device_id, org_id)
    rows = db.session.query(DeviceSetting).filter_by(device_id=device_id).order_by(DeviceSetting.key).all()
    return [r.to_dict() for r in rows]


def upsert_device_setting(device_id: int, org_id: int, key: str, value: str | None, user_id: int) -> dict:
    device = _require_device_in_org(device_id, org_id)
    row = db.session.query(DeviceSetting).filter_by(device_id=device_id, key=key).first()
    old_value = row.value if row else None
    action = "updated" if row else "created"
    if row:
        row.value = value
        row.updated_by_user_id = user_id
    else:
        row = DeviceSetting(device_id=device_id, key=key, value=value, updated_by_user_id=user_id)
        db.session.add(row)
        db.session.flush()

    append_ledger_event(
        store_id=device.store_id,
        event_type=f"device.setting_{action}",
        event_category="device",
        entity_type="device_setting",
        entity_id=row.id,
        actor_user_id=user_id,
        register_id=device.id,
        note=f"Device setting '{key}' {action}",
        payload=json.dumps({"key": key, "from": old_value, "to": value}),
    )
    db.session.commit()
    return row.to_dict()
