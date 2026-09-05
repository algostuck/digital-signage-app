import { Button, Typography } from "antd";
import { Link } from "react-router-dom";
import { ChartFrame } from "@/design-system";
import type { ApprovalItem } from "../types";
import { ViewAll, When } from "./shared";

/** Only rendered when the server included it — i.e. the caller can
 * approve. Viewers and content managers without that right never see it. */
export function ApprovalsWidget({
  items,
  loading,
  error,
  onRetry,
}: {
  items?: ApprovalItem[];
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  return (
    <ChartFrame
      title="Pending approval"
      extra={<ViewAll to="/approvals?state=pending" />}
      loading={loading && !items}
      error={error}
      onRetry={onRetry}
      empty={!!items && items.length === 0}
      emptyTitle="Nothing waiting on you"
      emptyDescription="Submitted campaigns and templates queue here."
    >
      <ul className="m-0 list-none p-0 dsc-divided">
        {items?.map((row) => (
          <li key={row.id} className="flex items-center gap-3 py-2">
            <div className="min-w-0 flex-1">
              <Typography.Text strong ellipsis className="block">
                {row.entity_name ?? `${row.entity_type} request`}
              </Typography.Text>
              <Typography.Text type="secondary" className="block text-xs">
                {row.entity_type} · submitted by {row.requester_name ?? "unknown"} · <When iso={row.submitted_at} />
              </Typography.Text>
            </div>
            <Link to="/approvals?state=pending">
              <Button size="small" type="primary">
                Review
              </Button>
            </Link>
          </li>
        ))}
      </ul>
    </ChartFrame>
  );
}
