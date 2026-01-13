# backend/app/config.py
from __future__ import annotations
import os


class Config:
    # Keep this simple for now; we can move to env vars later.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # SQLite DB stored in backend/instance/apos.sqlite3
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///apos.sqlite3",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEBUG_SEED_ENABLED = False

