import { Progress, Typography } from "antd";
import { Link } from "react-router-dom";
import { StatusBadge } from "@/design-system";
import { ToneTag } from "@/design-system";
import { ChartFrame } from "@/design-system";
import { StackedColumn } from "../charts/StackedColumn";
import { STATUS_COLORS } from "../charts/theme";
import type { DeploymentsBlock } from "../types";
import { dayLabel, ViewAll, When } from "./shared";

const STATUS_ORDER = ["publishing", "partial", "published", "failed", "queued", "cancelled"];

export function DeploymentWidget({
  deployments,
  loading,
  error,
  onRetry,
  rangeLabel,
}: {
  deployments?: DeploymentsBlock;
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
  rangeLabel: string;
}) {
  const total = deployments ? Object.values(deployments.by_status).reduce((n, v) => n + v, 0) : 0;
  const inRange = deployments?.history.some((h) => h.acknowledged + h.failed + h.pending > 0);
  const summary = deployments
    ? `${total} deployments in total; ${deployments.failed_devices_in_range} screen${deployments.failed_devices_in_range === 1 ? "" : "s"} failed to acknowledge ${rangeLabel.toLowerCase()}.`
    : undefined;

  return (
    <ChartFrame
      title="Deployments"
      extra={<ViewAll to="/deployments" />}
      summary={summary}
      loading={loading && !deployments}
      error={error}
      onRetry={onRetry}
      empty={!!deployments && total === 0}
      emptyTitle="Nothing published yet"
      emptyDescription="Publish a campaign to see its rollout here."
    >
      {deployments && (
        <>
          <div className="mb-3 flex flex-wrap gap-2" aria-label="Deployments by status">
            {STATUS_ORDER.filter((s) => (deployments.by_status[s] ?? 0) > 0).map((s) => (
              <Link key={s} to={`/deployments?status=${s}`} className="no-underline">
                <span className="inline-flex items-center gap-1">
                  <StatusBadge status={s} />
                  <Typography.Text strong style={{ fontSize: 12 }}>
                    {deployments.by_status[s]}
                  </Typography.Text>
                </span>
              </Link>
            ))}
          </div>
          {inRange && (
            <StackedColumn
              height={160}
              xLabel={dayLabel}
              series={[
                { key: "acknowledged", label: "Acknowledged", color: STATUS_COLORS.acknowledged, points: deployments.history.map((h) => ({ x: h.date, y: h.acknowledged })) },
                { key: "pending", label: "Pending", color: STATUS_COLORS.pending, points: deployments.history.map((h) => ({ x: h.date, y: h.pending })) },
                { key: "failed", label: "Failed", color: STATUS_COLORS.failed, points: deployments.history.map((h) => ({ x: h.date, y: h.failed })) },
              ]}
            />
          )}
          <ul className="m-0 mt-2 list-none p-0 dsc-divided">
            {deployments.recent.map((d) => (
              <li key={d.id} className="py-2">
                <div className="flex items-center gap-2">
                  <Typography.Text strong ellipsis className="min-w-0 flex-1">
                    {d.campaign_name}
                  </Typography.Text>
                  <Typography.Text type="secondary" className="text-xs">
                    v{d.version}
                  </Typography.Text>
                  <StatusBadge status={d.status} />
                  <When iso={d.created_at} />
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <Progress
                    percent={d.total_devices ? Math.round((d.acknowledged / d.total_devices) * 100) : 0}
                    size="small"
                    status={d.failed || d.status === "published" ? "normal" : "active"}
                    strokeColor={d.failed ? STATUS_COLORS.failed : d.status === "published" ? STATUS_COLORS.acknowledged : undefined}
                    format={() => `${d.acknowledged}/${d.total_devices}`}
                    className="flex-1" style={{ marginBottom: 0 }}
                    aria-label={`${d.acknowledged} of ${d.total_devices} screens acknowledged`}
                  />
                  {d.failed > 0 && (
                    <ToneTag tone="error" style={{ marginInlineEnd: 0 }}>
                      {d.failed} failed
                    </ToneTag>
                  )}
                  {d.pending > 0 && (
                    <ToneTag tone="default" style={{ marginInlineEnd: 0 }}>
                      {d.pending} pending
                    </ToneTag>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </ChartFrame>
  );
}
