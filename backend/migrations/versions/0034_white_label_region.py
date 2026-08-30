"""Phase-3 slice 3E-2: white label + regional tenancy metadata.

Branding stays in organizations.branding_json; white-label domain/email
identity live in settings_json (no DDL). The only DDL is the residency
region column.

Revision ID: 0034
Revises: 0033
Create Date: 2026-08-30
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("region", sa.String(50), nullable=False, server_default="default"),
    )


def downgrade() -> None:
    op.drop_column("organizations", "region")
