"""Advanced campaigns + enterprise scheduling: variants, blackout windows,
monthly recurrence and exception dates.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Blackouts are schedules with kind='blackout' (documented reuse — no
    # separate table). Monthly recurrence + exception dates extend the
    # Phase-1 recurrence model in place (P2-SCH-002).
    op.add_column(
        "schedules",
        sa.Column("kind", sa.String(20), nullable=False, server_default="play"),
    )
    op.add_column("schedules", sa.Column("recurrence_json", JSONType(), nullable=True))
    op.add_column(
        "schedules", sa.Column("exception_dates_json", JSONType(), nullable=True)
    )

    op.create_table(
        "campaign_variants",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "campaign_id",
            GUID(),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "layout_id", GUID(), sa.ForeignKey("layouts.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "playlist_id",
            GUID(),
            sa.ForeignKey("playlists.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("campaign_id", "name", name="uq_campaign_variants_name"),
    )
    op.create_index("ix_campaign_variants_campaign_id", "campaign_variants", ["campaign_id"])

    op.create_table(
        "campaign_variant_targets",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "variant_id",
            GUID(),
            sa.ForeignKey("campaign_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", GUID(), nullable=False),
        sa.Column("include_descendants", sa.Boolean(), nullable=False),
        sa.UniqueConstraint(
            "variant_id", "target_type", "target_id", name="uq_campaign_variant_targets"
        ),
    )
    op.create_index(
        "ix_campaign_variant_targets_variant_id", "campaign_variant_targets", ["variant_id"]
    )


def downgrade() -> None:
    op.drop_table("campaign_variant_targets")
    op.drop_table("campaign_variants")
    op.drop_column("schedules", "exception_dates_json")
    op.drop_column("schedules", "recurrence_json")
    op.drop_column("schedules", "kind")
