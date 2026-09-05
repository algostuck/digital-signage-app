import {
  CrownOutlined,
  DownOutlined,
  LogoutOutlined,
  SettingOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Avatar, Button, Dropdown, Flex, Typography, theme, type MenuProps } from "antd";
import { useNavigate } from "react-router-dom";
import { SHELL } from "@/design-system";
import { useAuth } from "../../lib/auth";
import { useEntitlements } from "../../lib/entitlements";

/**
 * Sticky account surface at the foot of the sidebar. Identity and plan
 * come from the live session and the entitlements endpoint — nothing here
 * is hard-coded. Destinations are limited to routes that actually exist.
 * The trigger is an antd text Button so hover, focus and keyboard
 * behaviour come from the component system, not hand-written CSS.
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
        <Typography.Text type="secondary" ellipsis style={{ display: "block", maxWidth: 224, fontSize: token.fontSizeSM }}>
          {user?.email ?? "Signed in"}
        </Typography.Text>
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
    <Flex
      align="center"
      style={{
        height: SHELL.headerHeight,
        flexShrink: 0,
        paddingInline: token.paddingXS,
        borderTop: `1px solid ${token.colorBorderSecondary}`,
      }}
    >
      <Dropdown menu={{ items }} trigger={["click"]} placement="topRight" arrow>
        <Button
          type="text"
          block
          aria-label={`Account menu for ${user?.full_name ?? "current user"}`}
          style={{
            height: "auto",
            paddingBlock: token.paddingXS,
            paddingInline: token.paddingXS,
            justifyContent: collapsed ? "center" : "flex-start",
          }}
        >
          <Flex align="center" gap={12} style={{ width: "100%", minWidth: 0 }}>
            <Avatar size={collapsed ? 32 : 36} icon={<UserOutlined />} style={{ flexShrink: 0 }} />
            {!collapsed && (
              <>
                <Flex vertical style={{ minWidth: 0, flex: 1, lineHeight: 1.2 }} align="flex-start">
                  <Typography.Text strong ellipsis style={{ display: "block", width: "100%" }}>
                    {user?.full_name ?? "—"}
                  </Typography.Text>
                  <Typography.Text
                    type="secondary"
                    ellipsis
                    style={{ display: "block", width: "100%", fontSize: token.fontSizeSM }}
                  >
                    {planLabel}
                  </Typography.Text>
                </Flex>
                <DownOutlined style={{ color: token.colorTextTertiary, fontSize: token.fontSizeSM, flexShrink: 0 }} aria-hidden />
              </>
            )}
          </Flex>
        </Button>
      </Dropdown>
    </Flex>
  );
}
