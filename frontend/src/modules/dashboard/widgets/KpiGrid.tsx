import {
  CloudUploadOutlined,
  DesktopOutlined,
  DisconnectOutlined,
  PlayCircleOutlined,
  RocketOutlined,
  WifiOutlined,
} from "@ant-design/icons";
import { Col, Row } from "antd";
import { GRID, KpiCard } from "@/design-system";
import { formatCompact, pct } from "../api";
import type { Kpis } from "../types";

/** Six executive numbers, strongest first, on the design-system KpiCard.
 * Each card leads somewhere with its filter already applied; none is
 * decorative. 2-up on phones, 3-up on tablets, 6-up on desktop. */
export function KpiGrid({ kpis, loading, rangeLabel }: { kpis?: Kpis; loading: boolean; rangeLabel: string }) {
  if (!kpis && !loading) return null;
  const d = kpis?.devices;
  const onlinePct = d ? pct(d.online, d.active) : null;
  const inProgress = kpis ? kpis.deployments.publishing + kpis.deployments.partial : 0;
  const completion = kpis?.playback.completion_rate;

  const cards = [
    {
      key: "devices",
      node: (
        <KpiCard
          label="Devices"
          icon={<DesktopOutlined />}
          value={d?.total ?? 0}
          context={d ? `${d.active} active${d.pending ? ` · ${d.pending} pending approval` : ""}` : undefined}
          to="/devices"
          loading={loading && !kpis}
        />
      ),
    },
    {
      key: "online",
      node: (
        <KpiCard
          label="Online"
          icon={<WifiOutlined />}
          value={d?.online ?? 0}
          suffix={onlinePct != null ? `${onlinePct}%` : undefined}
          context={
            !d
              ? undefined
              : d.active === 0
                ? "No active displays"
                : d.online === 0
                  ? "No display is reporting"
                  : d.warning
                    ? `${d.warning} with a warning`
                    : "All reporting on time"
          }
          tone={!d || d.active === 0 ? undefined : onlinePct != null && onlinePct < 80 ? "warning" : "success"}
          to="/devices?connection_status=online"
          loading={loading && !kpis}
        />
      ),
    },
    {
      key: "offline",
      node: (
        <KpiCard
          label="Offline"
          icon={<DisconnectOutlined />}
          value={d?.offline ?? 0}
          suffix={d?.active ? `${pct(d.offline, d.active)}%` : undefined}
          context={d ? (d.offline ? "No heartbeat past the offline threshold" : "Nothing offline") : undefined}
          tone={d?.offline ? "error" : "success"}
          to="/devices?connection_status=offline"
          loading={loading && !kpis}
        />
      ),
    },
    {
      key: "campaigns",
      node: (
        <KpiCard
          label="Live campaigns"
          icon={<RocketOutlined />}
          value={kpis?.campaigns.published ?? 0}
          context={
            kpis
              ? kpis.campaigns.pending_approval
                ? `${kpis.campaigns.pending_approval} awaiting approval`
                : `${kpis.campaigns.draft} draft · ${kpis.campaigns.paused} paused`
              : undefined
          }
          tone={kpis?.campaigns.pending_approval ? "warning" : undefined}
          to="/campaigns?status=published"
          loading={loading && !kpis}
        />
      ),
    },
    {
      key: "playback",
      node: (
        <KpiCard
          label="Playback"
          icon={<PlayCircleOutlined />}
          value={kpis ? formatCompact(kpis.playback.plays) : 0}
          suffix={completion != null ? `${completion}% completed` : undefined}
          context={kpis ? `${rangeLabel} · ${kpis.playback.devices} screens reporting` : undefined}
          to="/reports"
          loading={loading && !kpis}
        />
      ),
    },
    {
      key: "deployments",
      node: (
        <KpiCard
          label="Deployments"
          icon={<CloudUploadOutlined />}
          value={inProgress}
          suffix="in progress"
          context={kpis ? (kpis.deployments.failed ? `${kpis.deployments.failed} failed` : `${kpis.deployments.published} completed`) : undefined}
          tone={kpis?.deployments.failed ? "error" : undefined}
          to={kpis?.deployments.failed ? "/deployments?status=failed" : "/deployments"}
          loading={loading && !kpis}
        />
      ),
    },
  ];

  return (
    <Row gutter={GRID.gutter}>
      {cards.map((card) => (
        <Col key={card.key} xs={12} md={8} xl={4}>
          {card.node}
        </Col>
      ))}
    </Row>
  );
}
