"""Authentication endpoint tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.integration
class TestRegister:
    async def test_register_creates_user(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert "id" in data
        assert "hashed_password" not in data

    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        resp = await client.post("/api/v1/auth/register", json={
            "email": test_user.email,
            "password": "SecurePass123!",
        })
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "SecurePass123!",
        })
        assert resp.status_code == 422

    async def test_register_with_full_name(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "named@example.com",
            "password": "SecurePass123!",
            "full_name": "Jane Doe",
        })
        assert resp.status_code == 201
        assert resp.json()["full_name"] == "Jane Doe"


@pytest.mark.integration
class TestLogin:
    async def test_login_success(self, client: AsyncClient, test_user: User):
        form = f"username={test_user.email}&password=TestPass123!"
        resp = await client.post(
            "/api/v1/auth/login",
            content=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        form = f"username={test_user.email}&password=WrongPassword!"
        resp = await client.post(
            "/api/v1/auth/login",
            content=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_email(self, client: AsyncClient):
        form = "username=nobody@example.com&password=TestPass123!"
        resp = await client.post(
            "/api/v1/auth/login",
            content=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    async def test_login_json_body_rejected(self, client: AsyncClient, test_user: User):
        resp = await client.post("/api/v1/auth/login", json={
            "username": test_user.email,
            "password": "TestPass123!",
        })
        assert resp.status_code == 422


@pytest.mark.integration
class TestMe:
    async def test_me_returns_current_user(
        self, client: AsyncClient, test_user: User, auth_headers: dict
    ):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == test_user.email

    async def test_me_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_me_rejects_malformed_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})
        assert resp.status_code == 401
