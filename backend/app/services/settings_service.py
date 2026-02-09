from __future__ import annotations

from ..extensions import db
from ..models import OrganizationSetting, DeviceSetting


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


def get_device_settings(device_id: int) -> list[dict]:
    rows = db.session.query(DeviceSetting).filter_by(device_id=device_id).order_by(DeviceSetting.key).all()
    return [r.to_dict() for r in rows]


def upsert_device_setting(device_id: int, key: str, value: str | None, user_id: int) -> dict:
    row = db.session.query(DeviceSetting).filter_by(device_id=device_id, key=key).first()
    if row:
        row.value = value
        row.updated_by_user_id = user_id
    else:
        row = DeviceSetting(device_id=device_id, key=key, value=value, updated_by_user_id=user_id)
        db.session.add(row)
    db.session.commit()
    return row.to_dict()
