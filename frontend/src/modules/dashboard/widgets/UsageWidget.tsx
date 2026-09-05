import { Progress, Typography } from "antd";
import { StatusBadge } from "@/design-system";
import { ChartFrame } from "../charts/ChartFrame";
import type { UsageBlock, UsageMetric } from "../types";
import { ViewAll } from "./shared";

function formatStorage(mb: number): string {
  if (mb >= 1024 * 1024) return `${(mb / (1024 * 1024)).toFixed(1).replace(/\.0$/, "")} TB`;
  if (mb >= 1024) return `${(mb / 1024).toFixed(1).replace(/\.0$/, "")} GB`;
  return `${mb.toFixed(mb < 10 ? 2 : 0)} MB`;
}

function Meter({ label, metric, format }: { label: string; metric: UsageMetric; format?: (n: number) => string }) {
  const fmt = format ?? ((n: number) => n.toLocaleString());
  // Sums arrive as strings when the server serialises a Decimal; never trust the type.
  const used = Number(metric.used) || 0;
  const limit = metric.limit == null ? null : Number(metric.limit);
  const share = limit ? used / limit : 0;
  // Thresholds match the platform's own usage notifications (80 %) and the
  // point at which growth is refused (the limit itself).
  const status = share >= 0.95 ? "exception" : share >= 0.8 ? "active" : "normal";
  return (
    <div className="py-1.5">
      <div className="flex items-baseline justify-between">
        <Typography.Text>{label}</Typography.Text>
        <Typography.Text type="secondary" className="tabular-nums text-xs">
          {fmt(used)} / {limit == null ? "unlimited" : fmt(limit)}
          {limit ? ` · ${Math.round(share * 100)}%` : ""}
        </Typography.Text>
      </div>
      <Progress
        percent={limit ? Math.min(100, Math.round(share * 100)) : 0}
        showInfo={false}
        size="small"
        status={status}
        className="!mb-0"
        aria-label={`${label} usage`}
      />
      {share >= 0.8 && limit && (
        <Typography.Text type={share >= 0.95 ? "danger" : "warning"} className="text-xs">
          {share >= 0.95 ? "At the plan limit — growth is blocked." : "Approaching the plan limit."}
        </Typography.Text>
      )}
    </div>
  );
}

export function UsageWidget({
  usage,
  loading,
  error,
  onRetry,
}: {
  usage?: UsageBlock;
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  return (
    <ChartFrame
      title="Subscription & usage"
      extra={<ViewAll to="/settings" label="Manage" />}
      loading={loading && !usage}
      error={error}
      onRetry={onRetry}
    >
      {usage && (
        <>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Typography.Text strong className="text-[15px]">
              {usage.plan_name ?? "No plan"}
            </Typography.Text>
            {usage.subscription_status && <StatusBadge status={usage.subscription_status} />}
            {usage.period_end && (
              <Typography.Text type="secondary" className="text-xs">
                {usage.billing_cycle ? `${usage.billing_cycle} · ` : ""}renews{" "}
                {new Date(usage.period_end).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
              </Typography.Text>
            )}
          </div>
          {!usage.plan_name && (
            <Typography.Paragraph type="secondary" className="text-xs">
              This organization has no subscription and runs without limits.
            </Typography.Paragraph>
          )}
          <Meter label="Devices" metric={usage.devices} />
          <Meter label="Users" metric={usage.users} />
          <Meter label="Locations" metric={usage.locations} />
          <Meter label="Storage" metric={usage.storage_mb} format={formatStorage} />
        </>
      )}
    </ChartFrame>
  );
}
