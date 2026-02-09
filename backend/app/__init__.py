# Overview: Flask app factory; configures extensions, registers blueprints, and CLI.

# backend/app/__init__.py
import os
from flask import Flask, request

from .config import Config
from .extensions import db, migrate



def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    env_db = os.environ.get("DATABASE_URL")
    if env_db:
        app.config["SQLALCHEMY_DATABASE_URI"] = env_db

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so Alembic can discover metadata reliably
    from . import models  # noqa: F401

    # Register blueprints
    from .routes.system import system_bp
    from .routes.products import products_bp
    from .routes.inventory import inventory_bp
    from .routes.ledger import ledger_bp
    from .routes.lifecycle import lifecycle_bp  # Document lifecycle
    from .routes.identifiers import identifiers_bp  # Identifiers
    from .routes.sales import sales_bp  # Sales documents
    from .routes.auth import auth_bp  # Authentication
    from .routes.registers import registers_bp  # Register management
    from .routes.payments import payments_bp  # Payment processing
    from .routes.returns import returns_bp  # Returns & COGS reversal
    from .routes.transfers import transfers_bp  # Inter-store transfers
    from .routes.counts import counts_bp  # Physical counts
    from .routes.stores import stores_bp  # Store management
    from .routes.reports import reports_bp  # Reporting & analytics
    from .routes.admin import admin_bp  # Admin: User and role management
    from .routes.vendors import vendors_bp  # Vendor management
    from .routes.receives import receives_bp  # Receive documents (replaces inventory/receive)
    from .routes.timekeeping import timekeeping_bp  # Timekeeping
    from .routes.documents import documents_bp  # Unified documents
    from .routes.analytics import analytics_bp  # Analytics
    from .routes.imports import imports_bp  # Imports
    from .routes.developer import developer_bp  # Developer tools
    from .routes.settings import settings_bp  # Settings (org + device)
    from .routes.communications import communications_bp  # Communications
    from .routes.promotions import promotions_bp  # Promotions

    app.register_blueprint(system_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(lifecycle_bp)
    app.register_blueprint(identifiers_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(registers_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(returns_bp)
    app.register_blueprint(transfers_bp)
    app.register_blueprint(counts_bp)
    app.register_blueprint(stores_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(vendors_bp)
    app.register_blueprint(receives_bp)
    app.register_blueprint(timekeeping_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(imports_bp)
    app.register_blueprint(developer_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(communications_bp)
    app.register_blueprint(promotions_bp)

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        allowed_origins = {
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        }
        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,PATCH,OPTIONS"
        return response

    # Register CLI commands
    from .cli import register_commands
    register_commands(app)

    return app
