import { Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { ChartFrame } from "../charts/ChartFrame";
import { Donut } from "../charts/Donut";
import { STATUS_COLORS, statusLabel } from "../charts/theme";
import { TrendLine } from "../charts/TrendLine";
import type { DeviceHealth } from "../types";
import { dayLabel, hourLabel, ViewAll } from "./shared";

export function DeviceHealthWidget({
  health,
  loading,
  error,
  onRetry,
}: {
  health?: DeviceHealth;
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  const navigate = useNavigate();
  const current = health?.current;
  const total = current ? current.online + current.warning + current.offline + current.na : 0;
  const active = current ? total - current.na : 0;

  const summary = current
    ? `${current.online} online, ${current.warning} with a warning and ${current.offline} offline of ${active} active displays` +
      (current.na ? `; ${current.na} not yet active.` : ".")
    : undefined;

  const trend = health?.trend ?? [];
  const xLabel = health?.trend_granularity === "hour" ? hourLabel : (iso: string) => dayLabel(iso.slice(0, 10));

  return (
    <ChartFrame
      title="Device health"
      extra={<ViewAll to="/monitoring" label="Monitoring" />}
      summary={summary}
      loading={loading && !health}
      error={error}
      onRetry={onRetry}
      empty={!!health && total === 0}
      emptyTitle="No devices enrolled"
      emptyDescription="Enroll a display to start seeing fleet health here."
    >
      {current && (
        <>
          <Donut
            centre={active ? `${Math.round((current.online / active) * 100)}%` : "—"}
            centreLabel="online"
            slices={[
              { key: "online", label: statusLabel("online"), value: current.online, color: STATUS_COLORS.online },
              { key: "warning", label: statusLabel("warning"), value: current.warning, color: STATUS_COLORS.warning },
              { key: "offline", label: statusLabel("offline"), value: current.offline, color: STATUS_COLORS.offline },
              { key: "na", label: statusLabel("na"), value: current.na, color: STATUS_COLORS.na },
            ]}
            onSelect={(key) =>
              navigate(key === "na" ? "/devices?status=pending" : `/devices?connection_status=${key}`)
            }
          />
          <div className="mt-4">
            <Typography.Text strong className="text-[13px]">
              Health trend
            </Typography.Text>
            <Typography.Text type="secondary" className="ms-2 text-xs">
              {health?.trend_granularity === "hour" ? "hourly" : "daily"} snapshots
            </Typography.Text>
            {trend.length >= 2 ? (
              <TrendLine
                height={180}
                xLabel={xLabel}
                series={[
                  { key: "online", label: "Online", color: STATUS_COLORS.online, points: trend.map((p) => ({ x: p.at, y: p.online })) },
                  { key: "warning", label: "Warning", color: STATUS_COLORS.warning, points: trend.map((p) => ({ x: p.at, y: p.warning })) },
                  { key: "offline", label: "Offline", color: STATUS_COLORS.offline, points: trend.map((p) => ({ x: p.at, y: p.offline })) },
                ]}
              />
            ) : (
              <Typography.Paragraph type="secondary" className="!mb-0 mt-2 text-xs">
                Health is captured hourly; the trend appears once two or more snapshots fall in the selected range.
              </Typography.Paragraph>
            )}
          </div>
        </>
      )}
    </ChartFrame>
  );
}
