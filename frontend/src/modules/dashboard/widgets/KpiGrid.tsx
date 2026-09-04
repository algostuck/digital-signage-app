import {
  CloudUploadOutlined,
  DesktopOutlined,
  DisconnectOutlined,
  PlayCircleOutlined,
  RocketOutlined,
  WifiOutlined,
} from "@ant-design/icons";
import { Card, Skeleton, Typography, theme } from "antd";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { BRAND } from "../../../theme/tokens";
import { formatCompact, pct } from "../api";
import type { Kpis } from "../types";

type Tone = "neutral" | "success" | "warning" | "error";

function KpiCard({
  label,
  value,
  sub,
  context,
  icon,
  tone = "neutral",
  to,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  context?: ReactNode;
  icon: ReactNode;
  tone?: Tone;
  to?: string;
}) {
  const { token } = theme.useToken();
  const color = { neutral: token.colorText, success: BRAND.success, warning: BRAND.warning, error: BRAND.error }[tone];
  const card = (
    <Card
      size="small"
      hoverable={!!to}
      className="h-full min-w-[168px] snap-start"
      styles={{ body: { padding: "13px 16px" } }}
    >
      <div className="flex items-center gap-2 text-[13px]" style={{ color: token.colorTextSecondary }}>
        <span aria-hidden>{icon}</span>
        <span className="font-medium uppercase tracking-wide">{label}</span>
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <Typography.Text strong style={{ fontSize: 28, lineHeight: 1.15, color }}>
          {value}
        </Typography.Text>
        {sub && (
          <Typography.Text type="secondary" className="text-[13px]">
            {sub}
          </Typography.Text>
        )}
      </div>
      {context && (
        <Typography.Text type="secondary" className="mt-1 block truncate text-xs">
          {context}
        </Typography.Text>
      )}
    </Card>
  );
  return to ? (
    <Link to={to} className="block h-full no-underline" aria-label={`${label}: open details`}>
      {card}
    </Link>
  ) : (
    card
  );
}

/** Six executive numbers, strongest first. Each card leads somewhere with
 * its filter already applied; none is decorative. */
export function KpiGrid({ kpis, loading, rangeLabel }: { kpis?: Kpis; loading: boolean; rangeLabel: string }) {
  if (loading && !kpis) {
    return (
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i} size="small">
            <Skeleton active paragraph={{ rows: 1 }} />
          </Card>
        ))}
      </div>
    );
  }
  if (!kpis) return null;
  const d = kpis.devices;
  const onlinePct = pct(d.online, d.active);
  const inProgress = kpis.deployments.publishing + kpis.deployments.partial;
  const completion = kpis.playback.completion_rate;

  return (
    <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-1 md:mx-0 md:grid md:grid-cols-3 md:overflow-visible md:px-0 xl:grid-cols-6">
      <KpiCard
        label="Devices"
        icon={<DesktopOutlined />}
        value={d.total}
        context={`${d.active} active${d.pending ? ` · ${d.pending} pending approval` : ""}`}
        to="/devices"
      />
      <KpiCard
        label="Online"
        icon={<WifiOutlined />}
        value={d.online}
        sub={onlinePct != null ? `${onlinePct}%` : undefined}
        context={d.warning ? `${d.warning} with a warning` : "All reporting on time"}
        tone={onlinePct != null && onlinePct < 80 ? "warning" : "success"}
        to="/devices?connection_status=online"
      />
      <KpiCard
        label="Offline"
        icon={<DisconnectOutlined />}
        value={d.offline}
        sub={d.active ? `${pct(d.offline, d.active)}%` : undefined}
        context={d.offline ? "No heartbeat past the offline threshold" : "Nothing offline"}
        tone={d.offline ? "error" : "success"}
        to="/devices?connection_status=offline"
      />
      <KpiCard
        label="Active campaigns"
        icon={<RocketOutlined />}
        value={kpis.campaigns.published}
        context={
          kpis.campaigns.pending_approval
            ? `${kpis.campaigns.pending_approval} awaiting approval`
            : `${kpis.campaigns.draft} draft · ${kpis.campaigns.paused} paused`
        }
        tone={kpis.campaigns.pending_approval ? "warning" : "neutral"}
        to="/campaigns?status=published"
      />
      <KpiCard
        label="Playback"
        icon={<PlayCircleOutlined />}
        value={formatCompact(kpis.playback.plays)}
        sub={completion != null ? `${completion}% completed` : undefined}
        context={`${rangeLabel} · ${kpis.playback.devices} screens reporting`}
        to="/reports"
      />
      <KpiCard
        label="Deployments"
        icon={<CloudUploadOutlined />}
        value={inProgress}
        sub="in progress"
        context={kpis.deployments.failed ? `${kpis.deployments.failed} failed` : `${kpis.deployments.published} completed`}
        tone={kpis.deployments.failed ? "error" : "neutral"}
        to={kpis.deployments.failed ? "/deployments?status=failed" : "/deployments"}
      />
    </div>
  );
}
