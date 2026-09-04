import { Typography, theme } from "antd";
import { Link } from "react-router-dom";

/** Sticky brand header. Pinned by the sidebar's flex column — it never
 * takes part in the navigation scroll. */
export function SidebarLogo({ collapsed }: { collapsed: boolean }) {
  const { token } = theme.useToken();

  return (
    <Link
      to="/dashboard"
      style={{ borderBottom: `1px solid ${token.colorBorderSecondary}` }}
      className={`flex h-[55px] shrink-0 items-center gap-3 no-underline ${
        collapsed ? "justify-center px-2" : "px-4"
      }`}
      aria-label="Digital Signage Cloud — go to dashboard"
    >
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white"
        style={{ background: token.colorPrimary }}
        aria-hidden
      >
        DS
      </span>
      {!collapsed && (
        <span className="min-w-0 leading-tight">
          <Typography.Text strong className="block truncate !text-[15px]">
            Digital Signage
          </Typography.Text>
          <Typography.Text type="secondary" className="block truncate !text-xs">
            Cloud Platform
          </Typography.Text>
        </span>
      )}
    </Link>
  );
}
