import { Typography } from "antd";
import { Link } from "react-router-dom";
import { ChartFrame } from "../charts/ChartFrame";
import type { ActivityItem } from "../types";
import { ENTITY_ROUTES, humanizeAction, ViewAll, When } from "./shared";

export function ActivityWidget({
  items,
  loading,
  error,
  onRetry,
}: {
  items?: ActivityItem[];
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  return (
    <ChartFrame
      title="Recent activity"
      extra={<ViewAll to="/audit" label="Audit log" />}
      loading={loading && !items}
      error={error}
      onRetry={onRetry}
      empty={!!items && items.length === 0}
      emptyTitle="No activity recorded yet"
    >
      <ul className="m-0 list-none p-0 divide-y divide-slate-200 dark:divide-slate-700">
        {items?.map((row) => {
          const to = ENTITY_ROUTES[row.entity_type];
          return (
            <li key={row.id} className="flex items-start gap-2 py-2">
              <div className="min-w-0 flex-1">
                <Typography.Text className="block">
                  {to ? <Link to={to}>{humanizeAction(row.action)}</Link> : humanizeAction(row.action)}
                  {row.entity_name && (
                    <Typography.Text type="secondary"> — {row.entity_name}</Typography.Text>
                  )}
                </Typography.Text>
                <Typography.Text type="secondary" className="block text-xs">
                  {row.user_name ?? "System"}
                </Typography.Text>
              </div>
              <When iso={row.created_at} />
            </li>
          );
        })}
      </ul>
    </ChartFrame>
  );
}
