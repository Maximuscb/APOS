# backend/app/__init__.py
from flask import Flask, request

from .config import Config
from .extensions import db, migrate



def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

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
    from .routes.lifecycle import lifecycle_bp  # Phase 1: Document lifecycle
    from .routes.identifiers import identifiers_bp  # Phase 2: Identifiers
    from .routes.sales import sales_bp  # Phase 3: Sales documents
    from .routes.auth import auth_bp  # Phase 4: Authentication
    from .routes.registers import registers_bp  # Phase 8: Register management
    from .routes.payments import payments_bp  # Phase 9: Payment processing
    from .routes.returns import returns_bp  # Phase 10: Returns & COGS reversal
    from .routes.transfers import transfers_bp  # Phase 11: Inter-store transfers
    from .routes.counts import counts_bp  # Phase 11: Physical counts
    from .routes.stores import stores_bp  # Phase 13: Store management
    from .routes.reports import reports_bp  # Phase 14: Reporting & analytics
    from .routes.admin import admin_bp  # Admin: User and role management

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
