from __future__ import annotations

from ..extensions import db
from ..models import User, Store, UserStoreManagerAccess


def get_manager_store_ids(user_id: int, *, include_primary: bool = True) -> set[int]:
    """
    Get store IDs where the user has managerial access.

    include_primary includes User.store_id as implicit managerial scope.
    """
    rows = db.session.query(UserStoreManagerAccess.store_id).filter_by(user_id=user_id).all()
    store_ids = {row[0] for row in rows}

    if include_primary:
        user = db.session.query(User).filter_by(id=user_id).first()
        if user and user.store_id is not None:
            store_ids.add(user.store_id)

    return store_ids


def user_can_manage_store(user_id: int, store_id: int | None) -> bool:
    if store_id is None:
        return False
    return store_id in get_manager_store_ids(user_id, include_primary=True)


def list_manager_access(user_id: int) -> list[UserStoreManagerAccess]:
    return (
        db.session.query(UserStoreManagerAccess)
        .filter_by(user_id=user_id)
        .order_by(UserStoreManagerAccess.store_id.asc())
        .all()
    )


def grant_manager_access(*, user_id: int, store_id: int, granted_by_user_id: int | None = None) -> UserStoreManagerAccess:
    user = db.session.query(User).filter_by(id=user_id).first()
    if not user:
        raise ValueError("User not found")

    store = db.session.query(Store).filter_by(id=store_id).first()
    if not store:
        raise ValueError("Store not found")

    if user.org_id != store.org_id:
        raise ValueError("Store does not belong to user's organization")

    existing = db.session.query(UserStoreManagerAccess).filter_by(user_id=user_id, store_id=store_id).first()
    if existing:
        return existing

    access = UserStoreManagerAccess(
        user_id=user_id,
        store_id=store_id,
        granted_by_user_id=granted_by_user_id,
    )
    db.session.add(access)
    db.session.commit()
    return access


def revoke_manager_access(*, user_id: int, store_id: int) -> bool:
    access = db.session.query(UserStoreManagerAccess).filter_by(user_id=user_id, store_id=store_id).first()
    if not access:
        return False

    db.session.delete(access)
    db.session.commit()
    return True
