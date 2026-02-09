from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z

class SecurityEvent(db.Model):
    """
    Security event audit log with tenant context.

    MULTI-TENANT: Security events are scoped to organizations for isolation.
    Events must include org_id (and store_id where applicable) for tenant filtering.

    WHY: Track permission checks, failed attempts, and security-relevant actions.
    Critical for detecting unauthorized access attempts and compliance.

    IMMUTABLE: Never update or delete. Append-only for audit integrity.
    """
    __tablename__ = "security_events"
    __table_args__ = (
        db.Index("ix_security_events_user_type", "user_id", "event_type"),
        db.Index("ix_security_events_occurred", "occurred_at"),
        db.Index("ix_security_events_org_occurred", "org_id", "occurred_at"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)

    # MULTI-TENANT: Tenant context for isolation
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True)  # Nullable for pre-auth events
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=True, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)  # Nullable for anonymous

    # Event classification
    event_type = db.Column(db.String(64), nullable=False, index=True)  # PERMISSION_DENIED, PERMISSION_GRANTED, LOGIN_FAILED, etc.
    resource = db.Column(db.String(128), nullable=True)  # e.g., "/api/inventory/adjust"
    action = db.Column(db.String(64), nullable=True)     # e.g., "POST", "APPROVE_ADJUSTMENT"

    # Event details
    success = db.Column(db.Boolean, nullable=False, index=True)
    reason = db.Column(db.Text, nullable=True)  # e.g., "Missing permission: APPROVE_ADJUSTMENTS"

    # Client context
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)

    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now(), index=True)

    organization = db.relationship("Organization", backref=db.backref("security_events", lazy=True))
    store = db.relationship("Store", backref=db.backref("security_events", lazy=True))
    user = db.relationship("User", backref=db.backref("security_events", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "store_id": self.store_id,
            "user_id": self.user_id,
            "event_type": self.event_type,
            "resource": self.resource,
            "action": self.action,
            "success": self.success,
            "reason": self.reason,
            "ip_address": self.ip_address,
            "occurred_at": to_utc_z(self.occurred_at),
        }
