from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.document import Document
from app.models.organization import Organization, OrganizationMembership
from app.models.user import User
from app.schemas.organization import (
    AddMemberRequest,
    OrganizationCreate,
    OrganizationDetail,
    OrganizationList,
    OrganizationMemberList,
    OrganizationMemberRead,
    OrganizationRead,
    OrganizationUpdate,
    RoleUpdateRequest,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("/", response_model=OrganizationRead, status_code=201)
async def create_organization(
    payload: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationRead:
    existing = (
        await db.execute(select(Organization).where(Organization.slug == payload.slug))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Organization slug already exists")

    org = Organization(name=payload.name, slug=payload.slug)
    db.add(org)
    await db.flush()

    membership = OrganizationMembership(
        user_id=current_user.id,
        organization_id=org.id,
        role="admin",
        is_default=True,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(org)

    return OrganizationRead.model_validate(org)


@router.get("/", response_model=OrganizationList)
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationList:
    stmt = (
        select(Organization)
        .join(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == current_user.id,
            Organization.is_active.is_(True),
        )
        .order_by(Organization.created_at.desc())
    )
    orgs = (await db.execute(stmt)).scalars().all()

    items = []
    for org in orgs:
        count_stmt = select(sa_func.count()).select_from(
            select(OrganizationMembership)
            .where(OrganizationMembership.organization_id == org.id)
            .subquery()
        )
        member_count = (await db.execute(count_stmt)).scalar() or 0
        org_read = OrganizationRead.model_validate(org)
        org_read.member_count = member_count
        items.append(org_read)

    return OrganizationList(items=items, total=len(items))


@router.get("/{org_id}", response_model=OrganizationDetail)
async def get_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationDetail:
    membership = await _get_membership(org_id, current_user.id, db)
    org = membership.organization

    doc_count_stmt = select(sa_func.count()).where(
        Document.organization_id == org.id, Document.status == "ready"
    )
    document_count = (await db.execute(doc_count_stmt)).scalar() or 0

    member_count_stmt = select(sa_func.count()).where(
        OrganizationMembership.organization_id == org.id
    )
    member_count = (await db.execute(member_count_stmt)).scalar() or 0

    detail = OrganizationDetail.model_validate(org)
    detail.document_count = document_count
    detail.member_count = member_count
    return detail


@router.patch("/{org_id}", response_model=OrganizationRead)
async def update_organization(
    org_id: uuid.UUID,
    payload: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationRead:
    membership = await _get_admin_membership(org_id, current_user.id, db)
    org = membership.organization

    if payload.name is not None:
        org.name = payload.name
    if payload.is_active is not None:
        org.is_active = payload.is_active

    await db.commit()
    await db.refresh(org)
    return OrganizationRead.model_validate(org)


@router.delete("/{org_id}", status_code=204)
async def delete_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    membership = await _get_admin_membership(org_id, current_user.id, db)
    org = membership.organization

    doc_count = (
        await db.execute(select(sa_func.count()).where(Document.organization_id == org.id))
    ).scalar() or 0
    if doc_count > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete organization with {doc_count} active documents. "
                "Reassign or delete them first."
            ),
        )

    await db.delete(org)
    await db.commit()


@router.get("/{org_id}/members", response_model=OrganizationMemberList)
async def list_members(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationMemberList:
    await _get_membership(org_id, current_user.id, db)

    stmt = (
        select(OrganizationMembership)
        .options(selectinload(OrganizationMembership.user))
        .where(OrganizationMembership.organization_id == org_id)
        .order_by(OrganizationMembership.created_at.asc())
    )
    memberships = (await db.execute(stmt)).scalars().all()

    items = [
        OrganizationMemberRead(
            id=m.id,
            user_id=m.user_id,
            email=m.user.email,
            full_name=m.user.full_name,
            role=m.role,
            created_at=m.created_at,
        )
        for m in memberships
    ]
    return OrganizationMemberList(items=items, total=len(items))


@router.post("/{org_id}/members", response_model=OrganizationMemberRead, status_code=201)
async def add_member(
    org_id: uuid.UUID,
    payload: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationMemberRead:
    await _get_admin_membership(org_id, current_user.id, db)

    user = (await db.execute(select(User).where(User.email == payload.email))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. They must register first.")

    existing = (
        await db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member")

    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=org_id,
        role=payload.role,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    return OrganizationMemberRead(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.patch("/{org_id}/members/{member_id}/role", response_model=OrganizationMemberRead)
async def update_member_role(
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrganizationMemberRead:
    await _get_admin_membership(org_id, current_user.id, db)

    membership = (
        await db.execute(
            select(OrganizationMembership)
            .options(selectinload(OrganizationMembership.user))
            .where(
                OrganizationMembership.id == member_id,
                OrganizationMembership.organization_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    membership.role = payload.role
    await db.commit()

    return OrganizationMemberRead(
        id=membership.id,
        user_id=membership.user_id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.delete("/{org_id}/members/{member_id}", status_code=204)
async def remove_member(
    org_id: uuid.UUID,
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await _get_admin_membership(org_id, current_user.id, db)

    membership = (
        await db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.id == member_id,
                OrganizationMembership.organization_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    # Count remaining admins
    admin_count = (
        await db.execute(
            select(sa_func.count()).where(
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.role == "admin",
                OrganizationMembership.id != member_id,
            )
        )
    ).scalar() or 0
    if membership.role == "admin" and admin_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove the last admin. Promote another member first.",
        )

    await db.delete(membership)
    await db.commit()


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _get_membership(
    org_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> OrganizationMembership:
    stmt = (
        select(OrganizationMembership)
        .options(selectinload(OrganizationMembership.organization))
        .where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    membership = (await db.execute(stmt)).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Organization not found or access denied")
    return membership


async def _get_admin_membership(
    org_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession
) -> OrganizationMembership:
    membership = await _get_membership(org_id, user_id, db)
    if membership.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required for this operation")
    return membership
