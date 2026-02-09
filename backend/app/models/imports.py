from __future__ import annotations

from ..extensions import db
from app.time_utils import to_utc_z

class ImportBatch(db.Model):
    """
    Import batch for staging and progressively posting data.

    WHY: Enterprise businesses have thousands of products and millions of sales.
    Imports must be resumable, chunked, idempotent, and asynchronous.

    LIFECYCLE:
    1. CREATED: Batch created, awaiting data upload
    2. STAGED: Raw data ingested into staging tables
    3. MAPPING: Assisted mapping in progress (unmapped entities detected)
    4. POSTING: Posting resolvable rows progressively
    5. COMPLETED: All rows posted or quarantined
    6. FAILED: Unrecoverable error

    DESIGN:
    - Nothing posts to real documents/ledgers initially
    - System detects unmapped products/users/registers
    - Provides mapping UI and bulk tools
    - Cannot fully post until references resolved
    - Foreign IDs preserved as metadata for traceability
    """
    __tablename__ = "import_batches"
    __table_args__ = (
        db.Index("ix_import_batches_org_status", "org_id", "status"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)

    # Import type: PRODUCTS, SALES, INVENTORY, CUSTOMERS, etc.
    import_type = db.Column(db.String(32), nullable=False, index=True)

    # Batch status
    status = db.Column(db.String(16), nullable=False, default="CREATED", index=True)

    # Source file information
    source_file_name = db.Column(db.String(255), nullable=True)
    source_file_format = db.Column(db.String(16), nullable=True)  # CSV, JSON, EXCEL

    # Row counts
    total_rows = db.Column(db.Integer, nullable=True)
    staged_rows = db.Column(db.Integer, nullable=True, default=0)
    mapped_rows = db.Column(db.Integer, nullable=True, default=0)
    posted_rows = db.Column(db.Integer, nullable=True, default=0)
    error_rows = db.Column(db.Integer, nullable=True, default=0)
    quarantined_rows = db.Column(db.Integer, nullable=True, default=0)

    # Progress tracking for resumability
    last_processed_row = db.Column(db.Integer, nullable=True, default=0)

    # Error message if FAILED
    error_message = db.Column(db.Text, nullable=True)

    # User attribution
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    version_id = db.Column(db.Integer, nullable=False, default=1)

    # Relationships
    organization = db.relationship("Organization", backref=db.backref("import_batches", lazy=True))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])

    __mapper_args__ = {"version_id_col": version_id}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "import_type": self.import_type,
            "status": self.status,
            "source_file_name": self.source_file_name,
            "source_file_format": self.source_file_format,
            "total_rows": self.total_rows,
            "staged_rows": self.staged_rows,
            "mapped_rows": self.mapped_rows,
            "posted_rows": self.posted_rows,
            "error_rows": self.error_rows,
            "quarantined_rows": self.quarantined_rows,
            "last_processed_row": self.last_processed_row,
            "error_message": self.error_message,
            "created_by_user_id": self.created_by_user_id,
            "created_at": to_utc_z(self.created_at),
            "started_at": to_utc_z(self.started_at) if self.started_at else None,
            "completed_at": to_utc_z(self.completed_at) if self.completed_at else None,
            "version_id": self.version_id,
        }

class ImportStagingRow(db.Model):
    """
    Individual staged row from an import batch.

    WHY: Raw data goes into staging first. Each row tracks its mapping
    and posting status separately for progressive processing.

    DESIGN:
    - raw_data stores the original JSON-serialized row
    - foreign_id preserves the original ID from source system
    - mapping_status tracks whether references are resolved
    - posted_entity_id links to the created entity after posting
    """
    __tablename__ = "import_staging_rows"
    __table_args__ = (
        db.Index("ix_import_staging_batch_status", "batch_id", "mapping_status"),
        db.Index("ix_import_staging_batch_row", "batch_id", "row_number"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=False, index=True)

    # Row position in original file (for error reporting)
    row_number = db.Column(db.Integer, nullable=False)

    # Raw data as JSON string
    raw_data = db.Column(db.Text, nullable=False)

    # Original ID from source system (preserved for traceability)
    foreign_id = db.Column(db.String(128), nullable=True, index=True)

    # Mapping status: PENDING, MAPPED, UNMAPPED, ERROR
    mapping_status = db.Column(db.String(16), nullable=False, default="PENDING", index=True)

    # Posting status: PENDING, POSTED, QUARANTINED, ERROR
    posting_status = db.Column(db.String(16), nullable=False, default="PENDING", index=True)

    # Validation/mapping errors
    error_message = db.Column(db.Text, nullable=True)

    # Unmapped references (JSON array of {field, value, entity_type})
    unmapped_references = db.Column(db.Text, nullable=True)

    # After posting, link to created entity
    posted_entity_type = db.Column(db.String(64), nullable=True)
    posted_entity_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    posted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    batch = db.relationship("ImportBatch", backref=db.backref("staging_rows", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "row_number": self.row_number,
            "raw_data": self.raw_data,
            "foreign_id": self.foreign_id,
            "mapping_status": self.mapping_status,
            "posting_status": self.posting_status,
            "error_message": self.error_message,
            "unmapped_references": self.unmapped_references,
            "posted_entity_type": self.posted_entity_type,
            "posted_entity_id": self.posted_entity_id,
            "created_at": to_utc_z(self.created_at),
            "posted_at": to_utc_z(self.posted_at) if self.posted_at else None,
        }

class ImportEntityMapping(db.Model):
    """
    Entity mappings for import batches.

    WHY: When importing data, foreign IDs from the source system need
    to be mapped to local entity IDs. This table stores those mappings.
    """
    __tablename__ = "import_entity_mappings"
    __table_args__ = (
        db.UniqueConstraint("batch_id", "entity_type", "foreign_id", name="uq_import_mapping"),
        db.Index("ix_import_mapping_batch_entity", "batch_id", "entity_type"),
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=False, index=True)

    # Entity type: PRODUCT, USER, REGISTER, STORE, VENDOR, etc.
    entity_type = db.Column(db.String(32), nullable=False)

    # Foreign ID from source system
    foreign_id = db.Column(db.String(128), nullable=False)

    # Local entity ID (after mapping)
    local_entity_id = db.Column(db.Integer, nullable=True)

    # Mapping status: PENDING, MAPPED, SKIPPED, CREATE_NEW
    status = db.Column(db.String(16), nullable=False, default="PENDING")

    # If CREATE_NEW, store the data for creation
    creation_data = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    mapped_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    batch = db.relationship("ImportBatch", backref=db.backref("entity_mappings", lazy=True))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "entity_type": self.entity_type,
            "foreign_id": self.foreign_id,
            "local_entity_id": self.local_entity_id,
            "status": self.status,
            "creation_data": self.creation_data,
            "created_at": to_utc_z(self.created_at),
            "mapped_at": to_utc_z(self.mapped_at) if self.mapped_at else None,
        }
