import { Progress, Typography, type TableProps } from "antd";
import { Link } from "react-router-dom";
import { DataTable } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { ToneTag } from "@/design-system";
import { ChartFrame } from "@/design-system";
import { STATUS_COLORS } from "../charts/theme";
import type { CampaignsBlock, TopCampaign } from "../types";
import { ViewAll, When } from "./shared";

const STATUS_ORDER = ["published", "approved", "pending_approval", "paused", "draft", "expired", "archived"];

export function CampaignWidget({
  campaigns,
  loading,
  error,
  onRetry,
  rangeLabel,
}: {
  campaigns?: CampaignsBlock;
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
  rangeLabel: string;
}) {
  const total = campaigns ? Object.values(campaigns.by_status).reduce((n, v) => n + v, 0) : 0;
  const statuses = STATUS_ORDER.filter((s) => (campaigns?.by_status[s] ?? 0) > 0);
  const summary = campaigns
    ? `${campaigns.by_status.published ?? 0} campaigns live of ${total}` +
      (campaigns.by_status.pending_approval ? `, ${campaigns.by_status.pending_approval} awaiting approval.` : ".")
    : undefined;

  const columns: TableProps<TopCampaign>["columns"] = [
    {
      title: "Campaign",
      dataIndex: "name",
      render: (name: string, c) => (
        <div className="min-w-0">
          <Link to={`/campaigns?status=${c.status}`} className="font-medium">
            {name}
          </Link>
          <div>
            <StatusBadge status={c.status} />
          </div>
        </div>
      ),
    },
    {
      title: `Plays (${rangeLabel})`,
      dataIndex: "plays",
      align: "right",
      render: (n: number) => <Typography.Text strong>{n.toLocaleString()}</Typography.Text>,
    },
    {
      title: "Delivery",
      responsive: ["md"],
      render: (_, c) =>
        c.devices ? (
          <div className="w-32">
            <Progress
              percent={Math.round((c.acknowledged / c.devices) * 100)}
              size="small"
              status="normal"
              strokeColor={c.failed ? STATUS_COLORS.failed : undefined}
              format={() => `${c.acknowledged}/${c.devices}`}
              aria-label={`${c.acknowledged} of ${c.devices} screens acknowledged`}
            />
            {c.failed > 0 && (
              <ToneTag tone="error">
                {c.failed} failed
              </ToneTag>
            )}
          </div>
        ) : (
          <Typography.Text type="secondary">Not deployed</Typography.Text>
        ),
    },
    { title: "Updated", dataIndex: "updated_at", responsive: ["lg"], render: (d: string | null) => <When iso={d} /> },
  ];

  return (
    <ChartFrame
      title="Campaigns"
      extra={<ViewAll to="/campaigns" />}
      summary={summary}
      loading={loading && !campaigns}
      error={error}
      onRetry={onRetry}
      empty={!!campaigns && total === 0}
      emptyTitle="No campaigns yet"
      emptyDescription="Create your first campaign to start publishing content to your network."
      emptyAction={<Link to="/campaigns">Create a campaign</Link>}
    >
      {campaigns && (
        <>
          <div className="mb-3 flex flex-wrap gap-2" aria-label="Campaigns by status">
            {statuses.map((s) => (
              <Link key={s} to={`/campaigns?status=${s}`} className="no-underline">
                <ToneTag tone="default" className="cursor-pointer" style={{ marginInlineEnd: 0 }}>
                  <span className="capitalize">{s.replace(/_/g, " ")}</span>{" "}
                  <strong>{campaigns.by_status[s]}</strong>
                </ToneTag>
              </Link>
            ))}
          </div>
          {total > 0 && (
            <div
              className="mb-4 flex h-2 overflow-hidden rounded-full"
              role="img"
              aria-label={statuses.map((s) => `${s.replace(/_/g, " ")} ${campaigns.by_status[s]}`).join(", ")}
            >
              {statuses.map((s, i) => (
                <div
                  key={s}
                  style={{
                    width: `${(campaigns.by_status[s] / total) * 100}%`,
                    background: ["#059669", "#0891B2", "#D97706", "#7C3AED", "#94A3B8", "#64748B", "#CBD5E1"][i % 7],
                  }}
                />
              ))}
            </div>
          )}
          <DataTable<TopCampaign>
            rowKey="id"
            density="compact"
            columns={columns}
            dataSource={campaigns.top}
            pagination={false}
            emptyTitle="No playback in this range"
            emptyDescription="Plays appear as screens report proof of play."
          />
        </>
      )}
    </ChartFrame>
  );
}
