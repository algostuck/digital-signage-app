"""Constraint tests for the auth/tenant baseline schema."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Organization, Permission, Role, User


async def _make_org(session, code="acme") -> Organization:
    org = Organization(name="Acme", code=code, status="active", timezone="UTC", locale="en")
    session.add(org)
    await session.flush()
    return org


async def test_organization_code_unique(db_session):
    await _make_org(db_session, "dup")
    db_session.add(
        Organization(name="Other", code="dup", status="active", timezone="UTC", locale="en")
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_user_email_unique_per_tenant_not_global(db_session):
    org_a = await _make_org(db_session, "a")
    org_b = await _make_org(db_session, "b")
    db_session.add(
        User(organization_id=org_a.id, email="x@example.com", full_name="X", status="active")
    )
    # Same email in another tenant is allowed.
    db_session.add(
        User(organization_id=org_b.id, email="x@example.com", full_name="X", status="active")
    )
    await db_session.flush()
    # Duplicate within the same tenant is rejected.
    db_session.add(
        User(organization_id=org_a.id, email="x@example.com", full_name="X2", status="active")
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_user_requires_organization(db_session):
    db_session.add(
        User(organization_id=None, email="y@example.com", full_name="Y", status="active")
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_role_permission_assignment_roundtrip(db_session):
    org = await _make_org(db_session)
    perm = Permission(code="content.create", description="Create content")
    role = Role(organization_id=org.id, name="Content Manager", is_system=False)
    role.permissions.append(perm)
    user = User(organization_id=org.id, email="cm@example.com", full_name="CM", status="active")
    user.roles.append(role)
    db_session.add_all([perm, role, user])
    await db_session.flush()
    db_session.expire_all()

    loaded = (
        await db_session.execute(select(User).where(User.email == "cm@example.com"))
    ).scalar_one()
    assert loaded.roles[0].name == "Content Manager"
    assert loaded.roles[0].permissions[0].code == "content.create"


async def test_uuid_primary_keys(db_session):
    org = await _make_org(db_session)
    assert isinstance(org.id, uuid.UUID)
