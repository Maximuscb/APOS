import unittest
from flask import Flask

from app.extensions import db
from app.models import Organization, Store, User, Register, SettingRegistry, SettingValue, SettingAudit
from app.services import settings_service
from app.services.settings_service import (
    SCOPE_ORG,
    SCOPE_STORE,
    SCOPE_DEVICE,
    SCOPE_USER,
    SettingsAuthorizationError,
)


class SettingsServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config.update(
            SECRET_KEY="test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(cls.app)
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        from app import models  # noqa: F401
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.ctx.pop()

    def setUp(self):
        db.session.query(SettingAudit).delete()
        db.session.query(SettingValue).delete()
        db.session.query(SettingRegistry).delete()
        db.session.query(Register).delete()
        db.session.query(User).delete()
        db.session.query(Store).delete()
        db.session.query(Organization).delete()
        db.session.commit()

        self.org = Organization(name="Test Org", code="TEST")
        db.session.add(self.org)
        db.session.flush()

        self.store = Store(org_id=self.org.id, name="Main", code="MAIN", timezone="UTC", tax_rate_bps=0)
        db.session.add(self.store)
        db.session.flush()

        self.device = Register(org_id=self.org.id, store_id=self.store.id, register_number="REG-1", name="Front")
        db.session.add(self.device)
        db.session.flush()

        self.admin = User(
            org_id=self.org.id,
            username="admin",
            email="admin@test.local",
            password_hash="x",
            store_id=self.store.id,
            is_active=True,
            is_developer=True,
        )
        self.cashier = User(
            org_id=self.org.id,
            username="cashier",
            email="cashier@test.local",
            password_hash="x",
            store_id=self.store.id,
            is_active=True,
            is_developer=False,
        )
        db.session.add(self.admin)
        db.session.add(self.cashier)
        db.session.commit()

    def _seed_registry(self):
        rows = [
            SettingRegistry(
                key="test.precedence",
                scope_allowed=["ORG", "STORE", "DEVICE", "USER"],
                value_type="string",
                default_value_json="system-default",
                validation_json={},
                description="test precedence key",
                category="test",
                subcategory="resolution",
                is_sensitive=False,
                is_developer_only=False,
                requires_restart=False,
                requires_reprice=False,
                requires_recalc=False,
            ),
            SettingRegistry(
                key="test.bool",
                scope_allowed=["ORG"],
                value_type="bool",
                default_value_json=False,
                validation_json={},
                description="test bool key",
                category="test",
                subcategory="validation",
                is_sensitive=False,
                is_developer_only=False,
                requires_restart=False,
                requires_reprice=False,
                requires_recalc=False,
            ),
            SettingRegistry(
                key="test.secret",
                scope_allowed=["ORG"],
                value_type="string",
                default_value_json=None,
                validation_json={},
                description="sensitive",
                category="test",
                subcategory="security",
                is_sensitive=True,
                is_developer_only=False,
                requires_restart=False,
                requires_reprice=False,
                requires_recalc=False,
            ),
        ]
        db.session.add_all(rows)
        db.session.commit()

    def test_precedence_resolution_user_over_device_store_org(self):
        self._seed_registry()
        db.session.add_all(
            [
                SettingValue(key="test.precedence", scope_type=SCOPE_ORG, scope_id=self.org.id, value_json="org"),
                SettingValue(key="test.precedence", scope_type=SCOPE_STORE, scope_id=self.store.id, value_json="store"),
                SettingValue(key="test.precedence", scope_type=SCOPE_DEVICE, scope_id=self.device.id, value_json="device"),
                SettingValue(key="test.precedence", scope_type=SCOPE_USER, scope_id=self.cashier.id, value_json="user"),
            ]
        )
        db.session.commit()

        effective = settings_service.resolve_effective_settings(
            org_id=self.org.id,
            store_id=self.store.id,
            device_id=self.device.id,
            user_id=self.cashier.id,
        )
        self.assertEqual(effective["test.precedence"]["value"], "user")
        self.assertEqual(effective["test.precedence"]["source"], "USER")

    def test_validation_enforced_for_invalid_bool(self):
        self._seed_registry()
        actor = settings_service.make_actor(user_id=self.admin.id)
        result = settings_service.bulk_upsert_scope_settings(
            actor=actor,
            scope_type=SCOPE_ORG,
            scope_id=self.org.id,
            updates=[{"key": "test.bool", "value_json": "not-a-bool"}],
        )
        self.assertEqual(len(result["updated"]), 0)
        self.assertGreater(len(result["errors"]), 0)

    def test_scope_authorization_denies_unprivileged_user(self):
        self._seed_registry()
        actor = settings_service.make_actor(user_id=self.cashier.id)
        with self.assertRaises(SettingsAuthorizationError):
            settings_service.get_scope_settings(actor=actor, scope_type=SCOPE_ORG, scope_id=self.org.id)

    def test_sensitive_settings_excluded_from_effective_payload(self):
        self._seed_registry()
        db.session.add(SettingValue(key="test.secret", scope_type=SCOPE_ORG, scope_id=self.org.id, value_json="secret"))
        db.session.commit()
        effective = settings_service.resolve_effective_settings(org_id=self.org.id)
        self.assertNotIn("test.secret", effective)

    def test_audit_row_created_on_update(self):
        self._seed_registry()
        actor = settings_service.make_actor(user_id=self.admin.id)
        result = settings_service.bulk_upsert_scope_settings(
            actor=actor,
            scope_type=SCOPE_ORG,
            scope_id=self.org.id,
            updates=[{"key": "test.bool", "value_json": True}],
        )
        self.assertEqual(len(result["errors"]), 0)
        audit = db.session.query(SettingAudit).filter_by(
            key="test.bool",
            scope_type=SCOPE_ORG,
            scope_id=self.org.id,
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.new_value_json, True)


if __name__ == "__main__":
    unittest.main()
