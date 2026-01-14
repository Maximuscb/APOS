# backend/app/__init__.py
from flask import Flask

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
    from .routes.lifecycle import lifecycle_bp  # Phase 5: Document lifecycle

    app.register_blueprint(system_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(lifecycle_bp)  # Phase 5: Document lifecycle


    return app
