import { Flex, Typography, theme } from "antd";
import { Link } from "react-router-dom";
import { SHELL } from "@/design-system";

/** Sticky brand header. Pinned by the sidebar's flex column — it never
 * takes part in the navigation scroll. */
export function SidebarLogo({ collapsed }: { collapsed: boolean }) {
  const { token } = theme.useToken();

  return (
    <Link
      to="/dashboard"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: collapsed ? "center" : "flex-start",
        gap: 12,
        height: SHELL.headerHeight,
        flexShrink: 0,
        paddingInline: collapsed ? token.paddingXS : token.padding,
        borderBottom: `1px solid ${token.colorBorderSecondary}`,
        textDecoration: "none",
      }}
      aria-label="Digital Signage Cloud — go to dashboard"
    >
      <Flex
        align="center"
        justify="center"
        style={{
          width: 36,
          height: 36,
          flexShrink: 0,
          borderRadius: token.borderRadius,
          background: token.colorPrimary,
          color: "#FFFFFF",
          fontWeight: 700,
          fontSize: token.fontSize,
        }}
        aria-hidden
      >
        DS
      </Flex>
      {!collapsed && (
        <Flex vertical style={{ minWidth: 0, lineHeight: 1.2 }}>
          <Typography.Text strong ellipsis style={{ display: "block", fontSize: token.fontSizeLG }}>
            Digital Signage
          </Typography.Text>
          <Typography.Text type="secondary" ellipsis style={{ display: "block", fontSize: token.fontSizeSM }}>
            Cloud Platform
          </Typography.Text>
        </Flex>
      )}
    </Link>
  );
}
