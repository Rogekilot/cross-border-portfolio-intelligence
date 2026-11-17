"""Explicit local-only synthetic opt-in. Run with loopback host, no access log.

PYTHONPATH=src uv run --no-cache --no-sync --frozen --offline uvicorn web_api.dev:app \
    --host 127.0.0.1 --port 8000 --no-access-log
"""
from web_api.app import create_app

app = create_app(enable_local_guest=True)
