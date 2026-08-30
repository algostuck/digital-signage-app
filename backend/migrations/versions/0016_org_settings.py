"""Tenant settings store: organizations.settings_json.

Introduced with slice 2F for per-tenant monitoring thresholds
(P2-MON-002); later slices add policy defaults and retention settings to
the same column. (The notification-rule tables originally planned for
0016 move to a later revision — documented in PHASE_2_DATABASE_CHANGES.)

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import JSONType

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("settings_json", JSONType(), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "settings_json")
