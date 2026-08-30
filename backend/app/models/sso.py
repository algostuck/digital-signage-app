"""Enterprise SSO models (P3-GLO-002, slice 3E-1).

OIDC authorization-code flow issuing the platform's EXISTING JWT pair —
RBAC is untouched; the IdP only authenticates. Secrets by reference:
`client_secret_ref` names a server environment variable, never a stored
value. Claim mapping controls email/name extraction, optional group→role
mapping and whether unknown users are auto-provisioned.
"""

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class SsoProvider(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "sso_providers"
    __table_args__ = (
        Index("uq_sso_providers_org", "organization_id", unique=True),  # one per tenant
    )

    protocol: Mapped[str] = mapped_column(String(20), nullable=False, default="oidc")
    issuer: Mapped[str] = mapped_column(String(500), nullable=False)
    client_id: Mapped[str] = mapped_column(String(200), nullable=False)
    client_secret_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    # Cached issuer discovery document (refreshed on test/connect).
    metadata_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    # {"email": "email", "name": "name", "groups": "groups",
    #  "role_map": {"idp-group": "Role name"}, "auto_provision": false,
    #  "default_role": "Viewer"}
    claim_mapping_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:  # never leak refs in logs accidentally
        return f"<SsoProvider org={self.organization_id} issuer={self.issuer}>"


__all__ = ["SsoProvider"]
