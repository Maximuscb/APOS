from __future__ import annotations

from app.extensions import db
from app.models import Store, StoreConfig
from app.services.concurrency import lock_for_update, run_with_retry


class StoreError(Exception):
    """Raised when store operations fail."""
    pass


def create_store(name: str, code: str | None = None, parent_store_id: int | None = None) -> Store:
    def _op():
        if not name:
            raise StoreError("Store name is required")

        if parent_store_id is not None:
            parent = db.session.query(Store).filter_by(id=parent_store_id).first()
            if not parent:
                raise StoreError("Parent store not found")

        store = Store(
            name=name,
            code=code,
            parent_store_id=parent_store_id,
        )

        db.session.add(store)
        db.session.commit()
        return store

    return run_with_retry(_op)


def update_store(
    store_id: int,
    *,
    name: str | None = None,
    code: str | None = None,
    parent_store_id: int | None = None
) -> Store:
    def _op():
        store = lock_for_update(db.session.query(Store).filter_by(id=store_id)).first()
        if not store:
            raise StoreError("Store not found")

        if parent_store_id is not None:
            if parent_store_id == store_id:
                raise StoreError("Store cannot be its own parent")
            parent = db.session.query(Store).filter_by(id=parent_store_id).first()
            if not parent:
                raise StoreError("Parent store not found")

        if name is not None:
            store.name = name
        if code is not None:
            store.code = code
        if parent_store_id is not None:
            store.parent_store_id = parent_store_id

        db.session.commit()
        return store

    return run_with_retry(_op)


def get_store(store_id: int) -> Store | None:
    return db.session.query(Store).filter_by(id=store_id).first()


def list_stores() -> list[Store]:
    return db.session.query(Store).order_by(Store.name.asc()).all()


def set_store_config(store_id: int, key: str, value: str | None) -> StoreConfig:
    def _op():
        if not key:
            raise StoreError("Config key is required")

        store = db.session.query(Store).filter_by(id=store_id).first()
        if not store:
            raise StoreError("Store not found")

        config = lock_for_update(
            db.session.query(StoreConfig).filter_by(store_id=store_id, key=key)
        ).first()
        if config:
            config.value = value
        else:
            config = StoreConfig(store_id=store_id, key=key, value=value)
            db.session.add(config)

        db.session.commit()
        return config

    return run_with_retry(_op)


def get_store_configs(store_id: int) -> list[StoreConfig]:
    return db.session.query(StoreConfig).filter_by(store_id=store_id).order_by(StoreConfig.key.asc()).all()


def get_store_config(store_id: int, key: str) -> StoreConfig | None:
    return db.session.query(StoreConfig).filter_by(store_id=store_id, key=key).first()


def get_descendant_store_ids(store_id: int, *, include_self: bool = True) -> list[int]:
    stores = db.session.query(Store).all()
    children_map: dict[int, list[int]] = {}
    for store in stores:
        if store.parent_store_id is None:
            continue
        children_map.setdefault(store.parent_store_id, []).append(store.id)

    result: list[int] = []
    if include_self:
        result.append(store_id)

    stack = list(children_map.get(store_id, []))
    while stack:
        current = stack.pop()
        if current in result:
            continue
        result.append(current)
        stack.extend(children_map.get(current, []))

    return result


def get_store_tree(store_id: int) -> dict:
    store = db.session.query(Store).filter_by(id=store_id).first()
    if not store:
        raise StoreError("Store not found")

    def _build(node: Store) -> dict:
        return {
            "store": node.to_dict(),
            "children": [_build(child) for child in node.child_stores],
        }

    return _build(store)
