# backend/app/routes/system.py
from flask import Blueprint

system_bp = Blueprint("system", __name__)

@system_bp.get("/health")
def health():
    return {"status": "ok"}
