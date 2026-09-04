import { RightOutlined } from "@ant-design/icons";
import { Tag, Tooltip, Typography } from "antd";
import { toneStyle, type Tone } from "../../../components/ui/tone";
import { useThemeMode } from "../../../theme/ThemeProvider";
import { Link } from "react-router-dom";
import { timeAgo } from "../../devices/types";
import type { Severity } from "../types";

export function ViewAll({ to, label = "View all" }: { to: string; label?: string }) {
  return (
    <Link to={to} className="text-[13px]">
      {label} <RightOutlined className="text-[10px]" />
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

const SEVERITY_META: Record<Severity, { tone: Tone; label: string }> = {
  critical: { tone: "error", label: "Critical" },
  high: { tone: "high", label: "High" },
  medium: { tone: "warning", label: "Medium" },
  info: { tone: "processing", label: "Info" },
};

export function SeverityTag({ severity }: { severity: Severity }) {
  const { mode } = useThemeMode();
  const meta = SEVERITY_META[severity];
  return (
    <Tag className="!me-0" style={toneStyle(meta.tone, mode)}>
      {meta.label}
    </Tag>
  );
}

/** Relative time with the exact timestamp on hover. */
export function When({ iso }: { iso: string | null | undefined }) {
  if (!iso) return <Typography.Text type="secondary">—</Typography.Text>;
  return (
    <Tooltip title={new Date(iso).toLocaleString()}>
      <Typography.Text type="secondary" className="whitespace-nowrap text-xs">
        {timeAgo(iso)}
      </Typography.Text>
    </Tooltip>
  );
}

/** "Sep 4" for either a plain date ("2026-09-04") or a full timestamp,
 * always in the viewer's local calendar so two points on the same day get
 * the same label and points on different days never share one. */
export function dayLabel(iso: string): string {
  const d = iso.length === 10 ? new Date(`${iso}T00:00:00`) : new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function hourLabel(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}
