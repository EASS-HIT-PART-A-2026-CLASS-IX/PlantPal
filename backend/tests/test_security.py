"""Session 11 security tests — login, role guards, and token expiry."""

from __future__ import annotations

import time
from datetime import timedelta

import pytest

from app.config import get_settings
from app.security import create_access_token


PLANT_PAYLOAD = {
    "name": "Test Plant",
    "species": "Test species",
    "location": "Office",
    "light_need": "low",
    "water_frequency_hours": 168,
    "health_status": "healthy",
    "notes": "",
}


class TestLogin:
    def test_login_returns_token(self, anon_client):
        settings = get_settings()
        resp = anon_client.post(
            "/token",
            data={
                "username": settings.default_editor_username,
                "password": settings.default_editor_password,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert "editor" in body["roles"]

    def test_login_rejects_bad_password(self, anon_client):
        resp = anon_client.post(
            "/token",
            data={"username": "gardener", "password": "wrong"},
        )
        assert resp.status_code == 401


class TestProtectedRoutes:
    def test_post_plant_requires_auth(self, anon_client):
        resp = anon_client.post("/plants/", json=PLANT_PAYLOAD)
        assert resp.status_code == 401

    def test_post_plant_viewer_role_forbidden(self, anon_client, viewer_token):
        resp = anon_client.post(
            "/plants/",
            json=PLANT_PAYLOAD,
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 403

    def test_post_plant_editor_role_ok(self, anon_client, editor_token):
        resp = anon_client.post(
            "/plants/",
            json=PLANT_PAYLOAD,
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert resp.status_code == 200

    def test_delete_plant_requires_auth(self, client, anon_client):
        created = client.post("/plants/", json=PLANT_PAYLOAD).json()
        resp = anon_client.delete(f"/plants/{created['id']}")
        assert resp.status_code == 401

    def test_get_plants_is_public(self, anon_client):
        """Read routes stay open for the EX2 Streamlit frontend."""
        resp = anon_client.get("/plants/")
        assert resp.status_code == 200


class TestTokenExpiry:
    def test_expired_token_rejected(self, anon_client):
        expired = create_access_token(
            subject="user",
            roles=["editor"],
            expires_delta=timedelta(seconds=-1),
        )
        resp = anon_client.post(
            "/plants/",
            json=PLANT_PAYLOAD,
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"].lower().startswith("token")

    def test_token_expiring_soon_still_works(self, anon_client):
        token = create_access_token(
            subject="user",
            roles=["editor"],
            expires_delta=timedelta(seconds=5),
        )
        resp = anon_client.post(
            "/plants/",
            json=PLANT_PAYLOAD,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestInvalidTokens:
    def test_garbage_token(self, anon_client):
        resp = anon_client.post(
            "/plants/",
            json=PLANT_PAYLOAD,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401
