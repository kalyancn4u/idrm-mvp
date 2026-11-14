"""Dashboard services — read-mostly aggregations, sync-flavoured."""

from __future__ import annotations

import enum


def enum_or_none(enum_cls: type[enum.Enum], value: str | None):
    """
    Turn a query-string value into an enum member, or None if it is empty or
    not one of the allowed values.

    Filters come straight from the URL. Passing an unknown word on to the
    database makes the query fail, so an unknown filter is simply ignored.
    """
    if not value:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        return None
