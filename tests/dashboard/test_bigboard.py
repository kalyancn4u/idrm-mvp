"""BigBoard page tests."""

from __future__ import annotations


def test_bigboard_requires_login(dash_client):
    r = dash_client.get("/dashboard/bigboard/")
    assert r.status_code == 302
    assert "/dashboard/auth/login" in r.headers["Location"]


def test_bigboard_data_requires_login(dash_client):
    r = dash_client.get("/dashboard/bigboard/data")
    assert r.status_code == 302


def test_default_widgets_list_covers_six(dash_app):
    """The BigBoard ships with six widgets."""
    from dashboard.blueprints.bigboard import DEFAULT_WIDGETS

    assert len(DEFAULT_WIDGETS) == 6
    assert "active_incidents" in DEFAULT_WIDGETS
    assert "personnel_summary" in DEFAULT_WIDGETS
    assert "unit_summary" in DEFAULT_WIDGETS
    assert "orgs_summary" in DEFAULT_WIDGETS
    assert "shift_coverage" in DEFAULT_WIDGETS
    assert "available_resources" in DEFAULT_WIDGETS
