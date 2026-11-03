from __future__ import annotations


async def test_health_imports():
    # A minimal smoke test to ensure the test runtime can import the app.
    from app.main import app  # noqa: F401

