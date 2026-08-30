"""Phase-3 slice 3E-3: advanced security — device identities, credential
lifecycle, security policies and violations.

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_identities",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "device_id", GUID(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("identity_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_device_identities_organization_id", "device_identities", ["organization_id"]
    )
    op.create_index(
        "uq_device_identities_device", "device_identities", ["device_id"], unique=True
    )

    op.create_table(
        "identity_credentials",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "identity_id",
            GUID(),
            sa.ForeignKey("device_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(32), nullable=False),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_identity_credentials_identity_id", "identity_credentials", ["identity_id"]
    )

    op.create_table(
        "security_policies",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("scope_type", sa.String(30), nullable=False),
        sa.Column("conditions_json", JSONType(), nullable=False),
        sa.Column("actions_json", JSONType(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_security_policies_organization_id", "security_policies", ["organization_id"]
    )
    op.create_index(
        "uq_security_policies_org_scope",
        "security_policies",
        ["organization_id", "scope_type"],
        unique=True,
    )

    op.create_table(
        "policy_violations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "policy_id",
            GUID(),
            sa.ForeignKey("security_policies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", GUID(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("detail", sa.String(500), nullable=True),
        sa.Column(
            "detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_policy_violations_organization_id", "policy_violations", ["organization_id"]
    )
    op.create_index(
        "ix_policy_violations_org_state", "policy_violations", ["organization_id", "state"]
    )


def downgrade() -> None:
    op.drop_table("policy_violations")
    op.drop_table("security_policies")
    op.drop_table("identity_credentials")
    op.drop_table("device_identities")
