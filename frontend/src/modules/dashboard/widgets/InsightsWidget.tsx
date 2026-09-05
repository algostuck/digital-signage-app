import { BulbOutlined } from "@ant-design/icons";
import { Button, Typography } from "antd";
import { Link } from "react-router-dom";
import { ChartFrame } from "@/design-system";
import type { Insight } from "../types";

/** Fleet-intelligence findings. Only present when the plan includes
 * fleet AI; every card carries the evidence behind it, and the action is
 * a recommendation — nothing executes from the dashboard. */
export function InsightsWidget({
  items,
  loading,
  error,
  onRetry,
}: {
  items?: Insight[];
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  return (
    <ChartFrame
      title={
        <span>
          <BulbOutlined className="me-2" aria-hidden />
          Insights
        </span>
      }
      loading={loading && !items}
      error={error}
      onRetry={onRetry}
      empty={!!items && items.length === 0}
      emptyTitle="No anomalies open"
      emptyDescription="Fleet intelligence scores every device against your rules each sweep."
    >
      <ul className="m-0 list-none p-0 divide-y divide-slate-200 dark:divide-slate-700">
        {items?.map((i) => (
          <li key={i.id} className="py-2.5">
            <Typography.Text strong className="block">
              {i.finding}
            </Typography.Text>
            {i.why && (
              <Typography.Text type="secondary" className="block text-xs">
                Evidence: {i.why}
              </Typography.Text>
            )}
            {i.action && (
              <Typography.Text className="mt-1 block text-[13px]">{i.action}</Typography.Text>
            )}
            <Link to={i.href} className="mt-1 inline-block">
              <Button size="small">Review device</Button>
            </Link>
          </li>
        ))}
      </ul>
    </ChartFrame>
  );
}
