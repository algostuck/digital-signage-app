import { CheckCircleOutlined } from "@ant-design/icons";
import { Button, Typography } from "antd";
import { Link } from "react-router-dom";
import { ChartFrame } from "../charts/ChartFrame";
import type { AttentionItem } from "../types";
import { SeverityTag } from "./shared";

/** The most useful section on the page: what needs the administrator,
 * ranked by severity, every row leading to the place it is fixed. */
export function AttentionWidget({
  items,
  loading,
  error,
  onRetry,
}: {
  items?: AttentionItem[];
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  const count = items?.length ?? 0;
  return (
    <ChartFrame
      title={
        <span>
          Needs attention
          {count > 0 && (
            <Typography.Text type="secondary" className="ms-2 text-[13px] font-normal">
              {count}
            </Typography.Text>
          )}
        </span>
      }
      loading={loading && !items}
      error={error}
      onRetry={onRetry}
    >
      {items && items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-6 text-center">
          <CheckCircleOutlined style={{ fontSize: 28, color: "#059669" }} aria-hidden />
          <Typography.Text strong>All clear</Typography.Text>
          <Typography.Text type="secondary" className="text-xs">
            No offline screens, failed deployments or pending approvals right now.
          </Typography.Text>
        </div>
      ) : (
        <ul className="m-0 list-none p-0 divide-y divide-slate-200 dark:divide-slate-700">
          {items?.map((item) => (
            <li key={item.key} className="flex items-start gap-3 py-2.5">
              <SeverityTag severity={item.severity} />
              <div className="min-w-0 flex-1">
                <Typography.Text strong className="block">
                  {item.label}
                </Typography.Text>
                {item.detail && (
                  <Typography.Text type="secondary" className="block text-xs">
                    {item.detail}
                  </Typography.Text>
                )}
              </div>
              <Link to={item.href} className="shrink-0">
                <Button size="small">{item.action}</Button>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </ChartFrame>
  );
}
