import { Button, Result, Space } from "antd";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

type ExceptionStatus = 403 | 404 | 500;

const DEFAULTS: Record<ExceptionStatus, { title: string; description: string }> = {
  403: {
    title: "You do not have access to this page",
    description: "Your role or plan does not include this area. Ask an administrator if you need it.",
  },
  404: {
    title: "We could not find that page",
    description: "The link may be out of date, or the item may have been removed.",
  },
  500: {
    title: "Something went wrong",
    description: "The page could not be shown. Reloading usually fixes it; if not, note the time and tell your administrator.",
  },
};

/**
 * Exception page (Ant Design research: illustration, code, description,
 * ≤ 2 suggested actions, friendly tone). Used by the router's error
 * element, the catch-all route, and the permission/plan guards.
 */
export function ExceptionPage({
  status,
  title,
  description,
  icon,
  actions,
}: {
  status: ExceptionStatus;
  title?: string;
  description?: ReactNode;
  icon?: ReactNode;
  /** Up to two actions; defaults to "Go to dashboard" (+ "Reload" for 500). */
  actions?: ReactNode;
}) {
  const fallback = DEFAULTS[status];
  return (
    <Result
      status={status === 403 ? "403" : status === 404 ? "404" : "500"}
      icon={icon}
      title={title ?? fallback.title}
      subTitle={description ?? fallback.description}
      extra={
        actions ?? (
          <Space>
            <Link to="/dashboard">
              <Button type="primary">Go to dashboard</Button>
            </Link>
            {status === 500 && <Button onClick={() => window.location.reload()}>Reload</Button>}
          </Space>
        )
      }
    />
  );
}
