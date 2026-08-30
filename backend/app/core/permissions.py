"""Permission catalogue and default system roles.

Codes follow `<domain>.<action>` (BRD §29). The catalogue is seeded into the
`permissions` table; endpoint guards reference these constants — never string
literals scattered through the code.
"""

PERMISSIONS: dict[str, str] = {
    "organization.view": "View organization settings",
    "organization.manage": "Manage organization settings",
    "users.view": "View users",
    "users.manage": "Create, update and deactivate users",
    "roles.view": "View roles and permissions",
    "roles.manage": "Create and update roles",
    "locations.view": "View location hierarchy",
    "locations.manage": "Manage location hierarchy",
    "devices.view": "View devices and groups",
    "devices.manage": "Register, edit and group devices",
    "devices.control": "Send remote commands to devices",
    "content.view": "View content library",
    "content.create": "Upload and create content",
    "content.edit": "Edit content metadata and versions",
    "content.delete": "Archive and delete content",
    "layouts.view": "View layouts and templates",
    "layouts.manage": "Create and edit layouts and templates",
    "widgets.manage": "Manage the widget catalogue",
    "playlists.view": "View playlists",
    "playlists.manage": "Create and edit playlists",
    "campaigns.view": "View campaigns",
    "campaigns.manage": "Create and edit campaigns",
    "campaigns.approve": "Approve or reject campaigns",
    "campaigns.publish": "Publish campaigns to devices",
    "schedules.view": "View schedules",
    "schedules.manage": "Create and edit schedules",
    "deployments.view": "View deployments",
    "deployments.manage": "Retry and cancel deployments",
    "monitoring.view": "View device monitoring",
    "releases.manage": "Manage player releases and staged rollouts",
    "incidents.manage": "Acknowledge and resolve incidents",
    "reports.view": "View reports",
    "reports.export": "Export reports as files",
    "audit.view": "View audit logs",
    "notifications.view": "View notifications",
    "settings.manage": "Manage platform settings",
    "api_keys.manage": "Manage API keys",
    "webhooks.manage": "Manage webhook subscriptions",
    "ads.view": "View ad inventory and bookings",
    "ads.manage": "Manage ad inventory and bookings",
    "billing.view": "View plan, subscription, usage and invoices",
    "billing.manage": "Change plans, cancel/reactivate the subscription",
    "members.manage": "Add, update and remove tenant members",
}

_ALL = sorted(PERMISSIONS)
_ALL_VIEW = sorted(code for code in PERMISSIONS if code.endswith(".view"))

# System roles: seeded with organization_id NULL, visible to every tenant.
SYSTEM_ROLES: dict[str, dict] = {
    "Organization Administrator": {
        "description": "Full administrative access to the organization",
        "permissions": _ALL,
    },
    "Content Manager": {
        "description": "Manages content, layouts, playlists, campaigns and schedules",
        "permissions": sorted(
            {
                *_ALL_VIEW,
                "content.create",
                "content.edit",
                "content.delete",
                "layouts.manage",
                "widgets.manage",
                "playlists.manage",
                "campaigns.manage",
                "campaigns.publish",
                "schedules.manage",
                "reports.export",
            }
        ),
    },
    "Device Manager": {
        "description": "Manages devices, groups and monitoring",
        "permissions": sorted(
            {
                *_ALL_VIEW,
                "devices.manage",
                "devices.control",
                "deployments.manage",
                "incidents.manage",
                "releases.manage",
            }
        ),
    },
    "Viewer": {
        "description": "Read-only access",
        "permissions": _ALL_VIEW,
    },
}
