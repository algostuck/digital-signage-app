import { RightOutlined } from "@ant-design/icons";
import { Tooltip, Typography, theme } from "antd";
import { Link } from "react-router-dom";
import { formatDateTime, formatDayShort, formatRelative, formatTime, StatusBadge } from "@/design-system";
import type { Severity } from "../types";

export function ViewAll({ to, label = "View all" }: { to: string; label?: string }) {
  const { token } = theme.useToken();
  return (
    <Link to={to} style={{ fontSize: token.fontSizeSM }}>
      {label} <RightOutlined style={{ fontSize: 10 }} aria-hidden />
    </Link>
  );
}

/** Where an activity row leads, by entity type. */
export const ENTITY_ROUTES: Record<string, string> = {
  campaign: "/campaigns",
  asset: "/content",
  device: "/devices",
  playlist: "/playlists",
  layout: "/design",
  location: "/locations",
  user: "/users",
  role: "/users",
  deployment: "/deployments",
  schedule: "/schedules",
  template: "/design",
  organization: "/settings",
};

/** CAMPAIGN_PUBLISHED → "Campaign published". */
export function humanizeAction(action: string): string {
  const words = action.toLowerCase().split("_");
  return words.map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w)).join(" ");
}

/** Severity pill from the shared status vocabulary. */
export function SeverityTag({ severity }: { severity: Severity }) {
  return <StatusBadge domain="severity" status={severity} size="small" />;
}

/** Relative time with the exact timestamp on hover. */
export function When({ iso }: { iso: string | null | undefined }) {
  const { token } = theme.useToken();
  if (!iso) return <Typography.Text type="secondary">—</Typography.Text>;
  return (
    <Tooltip title={formatDateTime(iso)}>
      <Typography.Text type="secondary" style={{ whiteSpace: "nowrap", fontSize: token.fontSizeSM }}>
        {formatRelative(iso)}
      </Typography.Text>
    </Tooltip>
  );
}

/** "5 Sep" for either a plain date ("2026-09-04") or a full timestamp, in
 * the viewer's local calendar so points on the same day share a label. */
export function dayLabel(iso: string): string {
  return formatDayShort(iso.length === 10 ? `${iso}T00:00:00` : iso);
}

export function hourLabel(iso: string): string {
  return formatTime(iso);
}
