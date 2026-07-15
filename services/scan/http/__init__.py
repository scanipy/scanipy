"""CMP-ORCH-01 — HTTP surface package (CLAR-DEPLOY-19).

``app.create_app`` is the FastAPI factory over the framework-agnostic handler
core in ``services/scan/api.py``; ``serde`` is the byte-level parse/serialise
boundary (the C-1 parse function lives there).
"""

from services.scan.http.app import create_app

__all__ = ["create_app"]
