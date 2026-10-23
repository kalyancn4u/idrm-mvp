"""Dashboard access control."""

from __future__ import annotations


def test_login_page_public(dash_client):
    r = dash_client.get("/dashboard/login")
    assert r.status_code == 200
    assert b"Staff Console" in r.data


def test_dashboard_redirects_anonymous(dash_client):
    r = dash_client.get("/dashboard/")
    assert r.status_code == 302
    assert "/dashboard/auth/login" in r.headers["Location"]


def test_wrong_credentials_rejected(dash_client):
    r = dash_client.post("/dashboard/auth/login",
                         data={"email": "nobody@x.example", "password": "wrong"})
    assert r.status_code == 401


def test_citizen_role_cannot_log_in(dash_app):
    # The role gate is enforced in the config, not the form
    allowed = dash_app.config["ALLOWED_DASHBOARD_ROLES"]
    assert "citizen" not in allowed
    assert "coordinator" in allowed
    assert "admin" in allowed

