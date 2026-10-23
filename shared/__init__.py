"""
IDRM — shared code used by both the FastAPI app and the Flask dashboard.

Import boundary:
    app/**       may import from shared/**
    dashboard/** may import from shared/**
    dashboard/** MUST NOT import from app/**
    app/**       MUST NOT import from dashboard/**

Enforced by `make lint`.
"""

__all__ = [
    "config",
    "logging",
    "security",
    "sessions",
    "db",
    "cache",
    "storage",
    "audit",
    "enums",
    "rate_limit",
]
