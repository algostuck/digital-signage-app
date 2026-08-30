"""Phase-3 slice 3E-1: enterprise SSO (OIDC) provider configuration.

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sso_providers",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("protocol", sa.String(20), nullable=False),
        sa.Column("issuer", sa.String(500), nullable=False),
        sa.Column("client_id", sa.String(200), nullable=False),
        sa.Column("client_secret_ref", sa.String(100), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=True),
        sa.Column("claim_mapping_json", JSONType(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_sso_providers_organization_id", "sso_providers", ["organization_id"])
    op.create_index("uq_sso_providers_org", "sso_providers", ["organization_id"], unique=True)


def downgrade() -> None:
    op.drop_table("sso_providers")
