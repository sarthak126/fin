"""
Pydantic schemas for User and Organization API requests/responses.
"""

from pydantic import BaseModel
from datetime import datetime
from models import UserRole


class OrganizationBase(BaseModel):
    name: str
    domain: str | None = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationResponse(OrganizationBase):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserBase(BaseModel):
    email: str
    name: str
    role: UserRole = UserRole.ANALYST


class UserCreate(UserBase):
    org_id: str


class UserResponse(UserBase):
    id: str
    org_id: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
