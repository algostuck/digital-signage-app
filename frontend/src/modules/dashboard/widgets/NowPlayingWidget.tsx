import { PlayCircleOutlined } from "@ant-design/icons";
import { Avatar, Typography } from "antd";
import { Link } from "react-router-dom";
import { StatusBadge } from "@/design-system";
import { ToneTag } from "@/design-system";
import { ChartFrame } from "@/design-system";
import type { NowPlayingItem } from "../types";
import { ViewAll, When } from "./shared";

/** What screens are showing. "Reported" rows are proof-of-play records
 * from the last 30 minutes; "Scheduled" rows are what an online screen is
 * due to show, resolved by the same function the player uses. The two
 * are labelled apart and never mixed. */
export function NowPlayingWidget({
  items,
  loading,
  error,
  onRetry,
}: {
  items?: NowPlayingItem[];
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  return (
    <ChartFrame
      title="Now playing across the network"
      extra={<ViewAll to="/monitoring" label="Monitoring" />}
      loading={loading && !items}
      error={error}
      onRetry={onRetry}
      empty={!!items && items.length === 0}
      emptyTitle="Nothing reported in the last 30 minutes"
      emptyDescription="Rows appear as online screens report playback or resolve a scheduled campaign."
    >
      <ul className="m-0 list-none p-0 dsc-divided">
        {items?.map((row) => (
          <li key={row.device_id} className="flex items-center gap-3 py-2">
            <Avatar
              shape="square"
              size={40}
              src={row.thumbnail_url ?? undefined}
              icon={<PlayCircleOutlined />}
              alt=""
            />
            <div className="min-w-0 flex-1">
              <Typography.Text strong ellipsis className="block">
                {row.asset_name ?? row.campaign_name ?? "Scheduled content"}
              </Typography.Text>
              <Typography.Text type="secondary" ellipsis className="block text-xs">
                {row.campaign_name && row.asset_name ? `${row.campaign_name} · ` : ""}
                <Link to={`/devices?q=${encodeURIComponent(row.device_name)}`}>{row.device_name}</Link>
                {row.location_name ? ` · ${row.location_name}` : ""}
              </Typography.Text>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <ToneTag tone={row.source === "reported" ? "success" : "processing"} style={{ marginInlineEnd: 0 }}>
                {row.source === "reported" ? "Reported" : "Scheduled"}
              </ToneTag>
              {row.source === "reported" ? (
                <When iso={row.reported_at} />
              ) : (
                row.connection_status && <StatusBadge status={row.connection_status} />
              )}
            </div>
          </li>
        ))}
      </ul>
    </ChartFrame>
  );
}
