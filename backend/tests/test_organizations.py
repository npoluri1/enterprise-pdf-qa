"""Organization endpoint tests for multi-tenant support."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrganizationMembership
from app.models.user import User


@pytest.mark.integration
class TestCreateOrganization:
    async def test_create_org_success(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/organizations/",
            headers=auth_headers,
            json={"name": "Acme Corp", "slug": "acme-corp"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["slug"] == "acme-corp"
        assert "id" in data

    async def test_create_org_duplicate_slug(
        self, client: AsyncClient, auth_headers: dict, test_organization: Organization
    ):
        resp = await client.post(
            "/api/v1/organizations/",
            headers=auth_headers,
            json={"name": "Another Org", "slug": test_organization.slug},
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    async def test_create_org_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/organizations/",
            json={"name": "Acme Corp", "slug": "acme-corp"},
        )
        assert resp.status_code == 401


@pytest.mark.integration
class TestListOrganizations:
    async def test_list_user_orgs(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_organization: Organization,
    ):
        resp = await client.get("/api/v1/organizations/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        slugs = [o["slug"] for o in data["items"]]
        assert test_organization.slug in slugs

    async def test_list_does_not_include_other_user_orgs(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
    ):
        other_user = User(
            email=f"other-org-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="hashed_placeholder",
        )
        db_session.add(other_user)
        await db_session.flush()

        other_org = Organization(
            name="Stealth Org",
            slug=f"stealth-{uuid.uuid4().hex[:8]}",
        )
        db_session.add(other_org)
        await db_session.flush()

        membership = OrganizationMembership(
            user_id=other_user.id,
            organization_id=other_org.id,
            role="admin",
        )
        db_session.add(membership)
        await db_session.commit()

        resp = await client.get("/api/v1/organizations/", headers=auth_headers)
        slugs = [o["slug"] for o in resp.json()["items"]]
        assert other_org.slug not in slugs


@pytest.mark.integration
class TestOrganizationDetail:
    async def test_get_org_detail(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_organization: Organization,
    ):
        resp = await client.get(
            f"/api/v1/organizations/{test_organization.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == test_organization.name
        assert "document_count" in data
        assert "member_count" in data

    async def test_get_org_not_member(self, client: AsyncClient, db_session: AsyncSession):
        from app.core.security import create_access_token

        other_user = User(
            email=f"outsider-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="hashed_placeholder",
        )
        db_session.add(other_user)
        await db_session.commit()
        token = create_access_token(other_user.id)
        headers = {"Authorization": f"Bearer {token}"}

        org = Organization(name="Private Org", slug=f"private-{uuid.uuid4().hex[:8]}")
        db_session.add(org)
        await db_session.commit()

        resp = await client.get(
            f"/api/v1/organizations/{org.id}",
            headers=headers,
        )
        assert resp.status_code == 404


@pytest.mark.integration
class TestOrganizationMembers:
    async def test_list_members(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        test_organization: Organization,
    ):
        resp = await client.get(
            f"/api/v1/organizations/{test_organization.id}/members",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        emails = [m["email"] for m in data["items"]]
        assert test_user.email in emails

    async def test_add_member(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        new_user = User(
            email=f"new-member-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="hashed_placeholder",
        )
        db_session.add(new_user)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            headers=auth_headers,
            json={"email": new_user.email, "role": "member"},
        )
        assert resp.status_code == 201
        assert resp.json()["email"] == new_user.email

    async def test_add_member_duplicate(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_organization: Organization,
        test_user: User,
    ):
        resp = await client.post(
            f"/api/v1/organizations/{test_organization.id}/members",
            headers=auth_headers,
            json={"email": test_user.email, "role": "member"},
        )
        assert resp.status_code == 400

    async def test_remove_member(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        member_user = User(
            email=f"member-to-remove-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="hashed_placeholder",
        )
        db_session.add(member_user)
        await db_session.flush()

        membership = OrganizationMembership(
            user_id=member_user.id,
            organization_id=test_organization.id,
            role="member",
        )
        db_session.add(membership)
        await db_session.commit()

        resp = await client.delete(
            f"/api/v1/organizations/{test_organization.id}/members/{membership.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204


@pytest.mark.integration
class TestOrganizationUpdateDelete:
    async def test_update_org(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_organization: Organization,
    ):
        resp = await client.patch(
            f"/api/v1/organizations/{test_organization.id}",
            headers=auth_headers,
            json={"name": "Updated Corp"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Corp"

    async def test_delete_org(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
        test_user: User,
    ):
        org = Organization(name="Temp Org", slug=f"temp-{uuid.uuid4().hex[:8]}")
        db_session.add(org)
        await db_session.flush()

        membership = OrganizationMembership(
            user_id=test_user.id,
            organization_id=org.id,
            role="admin",
        )
        db_session.add(membership)
        await db_session.commit()

        resp = await client.delete(
            f"/api/v1/organizations/{org.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204
