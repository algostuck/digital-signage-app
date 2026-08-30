import {
  CrownOutlined,
  DownOutlined,
  LogoutOutlined,
  SettingOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Avatar, Dropdown, Typography, theme, type MenuProps } from "antd";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { useEntitlements } from "../../lib/entitlements";

/**
 * Sticky account surface at the foot of the sidebar. Identity and plan
 * come from the live session and the entitlements endpoint — nothing here
 * is hard-coded. Destinations are limited to routes that actually exist.
 */
export function AccountMenu({ collapsed }: { collapsed: boolean }) {
  const { user, logout, hasPermission } = useAuth();
  const { entitlements } = useEntitlements();
  const { token } = theme.useToken();
  const navigate = useNavigate();

  async function onLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  const items: MenuProps["items"] = [
    {
      key: "identity",
      type: "group",
      label: (
        <span className="block max-w-56 truncate text-xs">{user?.email ?? "Signed in"}</span>
      ),
    },
    ...(hasPermission("organization.view")
      ? [
          {
            key: "/settings",
            icon: <SettingOutlined />,
            label: "Organization settings",
            onClick: () => navigate("/settings"),
          },
        ]
      : []),
    ...(user?.is_superuser
      ? [
          {
            key: "/platform",
            icon: <CrownOutlined />,
            label: "Platform console",
            onClick: () => navigate("/platform"),
          },
        ]
      : []),
    { type: "divider" as const },
    {
      key: "signout",
      icon: <LogoutOutlined />,
      label: "Sign out",
      danger: true,
      onClick: onLogout,
    },
  ];

  const planLabel = entitlements?.plan_name ? `${entitlements.plan_name} plan` : "No plan assigned";

  return (
    <div
      className="flex h-16 shrink-0 items-center px-2"
      style={{ borderTop: `1px solid ${token.colorBorderSecondary}` }}
    >
      <Dropdown menu={{ items }} trigger={["click"]} placement="topRight" arrow>
        <button
          type="button"
          aria-label={`Account menu for ${user?.full_name ?? "current user"}`}
          className={`account-trigger flex w-full cursor-pointer items-center gap-3 border-0 bg-transparent px-2 py-2 text-left ${
            collapsed ? "justify-center" : ""
          }`}
          style={{ borderRadius: token.borderRadius }}
        >
          <Avatar size={collapsed ? 32 : 36} icon={<UserOutlined />} className="shrink-0" />
          {!collapsed && (
            <>
              <span className="min-w-0 flex-1 leading-tight">
                <Typography.Text strong className="block truncate !text-sm">
                  {user?.full_name ?? "—"}
                </Typography.Text>
                <Typography.Text type="secondary" className="block truncate !text-xs">
                  {planLabel}
                </Typography.Text>
              </span>
              <DownOutlined
                className="shrink-0 text-xs"
                style={{ color: token.colorTextTertiary }}
                aria-hidden
              />
            </>
          )}
        </button>
      </Dropdown>
    </div>
  );
}
