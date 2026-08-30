"""Location hierarchy: location_types, locations (materialized path), tags.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-29
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import GUID, JSONType

revision: str = "0003"
down_revision: str | None = "0002"
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
        "location_types",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint("organization_id", "code", name="uq_location_types_org_code"),
    )
    op.create_index("ix_location_types_organization_id", "location_types", ["organization_id"])

    op.create_table(
        "tags",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.String(200), nullable=False),
        *_audit_columns(),
        sa.UniqueConstraint("organization_id", "key", "value", name="uq_tags_org_key_value"),
    )
    op.create_index("ix_tags_organization_id", "tags", ["organization_id"])

    op.create_table(
        "locations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "organization_id",
            GUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "parent_id", GUID(), sa.ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column(
            "type_id",
            GUID(),
            sa.ForeignKey("location_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("path", sa.String(4000), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=True),
        *_audit_columns(),
        sa.UniqueConstraint(
            "organization_id", "parent_id", "code", name="uq_locations_org_parent_code"
        ),
    )
    op.create_index("ix_locations_organization_id", "locations", ["organization_id"])
    op.create_index("ix_locations_org_parent", "locations", ["organization_id", "parent_id"])
    op.create_index("ix_locations_org_path", "locations", ["organization_id", "path"])

    op.create_table(
        "location_tags",
        sa.Column(
            "location_id",
            GUID(),
            sa.ForeignKey("locations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id", GUID(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
        ),
    )


def downgrade() -> None:
    op.drop_table("location_tags")
    op.drop_table("locations")
    op.drop_table("tags")
    op.drop_table("location_types")
