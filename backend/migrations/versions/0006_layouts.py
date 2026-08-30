"""Layout engine: layouts, layout_versions, layout_zones, templates.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "layouts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("draft_canvas_json", JSONType(), nullable=False),
        sa.Column("current_version_id", GUID(), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_layouts_organization_id", "layouts", ["organization_id"])

    op.create_table(
        "layout_versions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "layout_id", GUID(), sa.ForeignKey("layouts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("canvas_json", JSONType(), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("layout_id", "version_no", name="uq_layout_versions_layout_no"),
    )
    op.create_index("ix_layout_versions_layout_id", "layout_versions", ["layout_id"])

    op.create_table(
        "layout_zones",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "layout_version_id",
            GUID(),
            sa.ForeignKey("layout_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("zone_key", sa.String(50), nullable=False),
        sa.Column("zone_json", JSONType(), nullable=False),
        sa.UniqueConstraint("layout_version_id", "zone_key", name="uq_layout_zones_version_key"),
    )
    op.create_index("ix_layout_zones_layout_version_id", "layout_zones", ["layout_version_id"])

    op.create_table(
        "templates",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "layout_id", GUID(), sa.ForeignKey("layouts.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("canvas_json", JSONType(), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint("organization_id", "name", name="uq_templates_org_name"),
    )
    op.create_index("ix_templates_organization_id", "templates", ["organization_id"])


def downgrade() -> None:
    op.drop_table("templates")
    op.drop_table("layout_zones")
    op.drop_table("layout_versions")
    op.drop_table("layouts")
