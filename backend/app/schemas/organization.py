from __future__ import annotations

from datetime import datetime
import uuid

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")


class OrganizationRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    member_count: int = 0
    model_config = {"from_attributes": True}


class OrganizationUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class OrganizationList(BaseModel):
    items: list[OrganizationRead]
    total: int


class OrganizationMemberRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    created_at: datetime
    model_config = {"from_attributes": True}


class OrganizationMemberList(BaseModel):
    items: list[OrganizationMemberRead]
    total: int


class AddMemberRequest(BaseModel):
    email: str
    role: str = Field(default="member", pattern=r"^(admin|member)$")


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(admin|member)$")


class OrganizationDetail(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    document_count: int = 0
    member_count: int = 0
    model_config = {"from_attributes": True}
