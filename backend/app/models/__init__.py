"""Import all models here so Base.metadata and Alembic see the full schema."""

from app.models.ai import AiOutput, AiPolicy, AiRequest
from app.models.approval import ApprovalAction, ApprovalPolicy, ApprovalRequest
from app.models.auth import RefreshToken
from app.models.campaign import (
    Campaign,
    CampaignTarget,
    CampaignVariant,
    CampaignVariantTarget,
    Deployment,
    DeploymentDevice,
    Schedule,
)
from app.models.content import (
    Asset,
    AssetVersion,
    Folder,
    UploadSession,
    asset_tags,
)
from app.models.data_source import DataSource, DataSourceSchema, DataSourceSnapshot
from app.models.decisioning import DecisionLog, DecisionPolicy, DecisionRule
from app.models.developer import ApiProduct, ApiVersion
from app.models.device import (
    Device,
    DeviceCapability,
    DeviceCommand,
    DeviceGroup,
    DeviceHeartbeat,
    Incident,
    Screenshot,
    device_tags,
)
from app.models.events import DomainEvent, EventDelivery, EventSubscription
from app.models.experiment import Experiment, ExperimentAssignment, ExperimentVariant
from app.models.integration import (
    ApiKey,
    WebhookDelivery,
    WebhookSubscription,
)
from app.models.layout import Layout, LayoutVersion, LayoutZone, Template, TemplateVersion
from app.models.location import Location, LocationType, Tag, location_tags
from app.models.notification_rule import NotificationDelivery, NotificationRule
from app.models.ops import AuditLog, DeviceEvent, Notification, PlaybackEvent
from app.models.organization import Organization
from app.models.playlist import Playlist, PlaylistItem, PlaylistVersion
from app.models.release import PlayerRelease, RolloutBatch, RolloutDevice
from app.models.saas import (
    Invoice,
    Payment,
    Plan,
    PlanChangeRequest,
    PlanEntitlement,
    Subscription,
    SubscriptionEvent,
    SubscriptionItem,
    TenantUser,
    UsageCounter,
    UsageEvent,
)
from app.models.saved_view import SavedView
from app.models.studio import (
    AssetCollection,
    AssetCollectionItem,
    Widget,
    WidgetVersion,
)
from app.models.user import Permission, Role, User, role_permissions, user_roles

__all__ = [
    "AiOutput",
    "AiPolicy",
    "AiRequest",
    "ApiProduct",
    "ApiVersion",
    "DataSource",
    "DecisionLog",
    "DecisionPolicy",
    "DecisionRule",
    "DataSourceSchema",
    "DataSourceSnapshot",
    "DomainEvent",
    "EventDelivery",
    "EventSubscription",
    "Experiment",
    "ExperimentAssignment",
    "ExperimentVariant",
    "Organization",
    "User",
    "Role",
    "Permission",
    "RefreshToken",
    "Location",
    "LocationType",
    "Tag",
    "location_tags",
    "Device",
    "DeviceGroup",
    "DeviceCapability",
    "DeviceCommand",
    "DeviceHeartbeat",
    "Screenshot",
    "Incident",
    "device_tags",
    "Layout",
    "LayoutVersion",
    "LayoutZone",
    "Template",
    "TemplateVersion",
    "Widget",
    "WidgetVersion",
    "AssetCollection",
    "AssetCollectionItem",
    "Playlist",
    "PlaylistItem",
    "PlaylistVersion",
    "Campaign",
    "Schedule",
    "CampaignTarget",
    "CampaignVariant",
    "CampaignVariantTarget",
    "Deployment",
    "DeploymentDevice",
    "PlayerRelease",
    "RolloutBatch",
    "RolloutDevice",
    "ApprovalPolicy",
    "ApprovalRequest",
    "ApprovalAction",
    "AuditLog",
    "Notification",
    "NotificationRule",
    "NotificationDelivery",
    "WebhookSubscription",
    "WebhookDelivery",
    "ApiKey",
    "SavedView",
    "TenantUser",
    "Plan",
    "PlanChangeRequest",
    "PlanEntitlement",
    "Subscription",
    "SubscriptionItem",
    "SubscriptionEvent",
    "UsageCounter",
    "UsageEvent",
    "Invoice",
    "Payment",
    "DeviceEvent",
    "PlaybackEvent",
    "Folder",
    "Asset",
    "AssetVersion",
    "UploadSession",
    "asset_tags",
    "user_roles",
    "role_permissions",
]
