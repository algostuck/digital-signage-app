import { Button, Empty, Result, Skeleton, Typography, theme } from "antd";
import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  /** Why it is empty, in one sentence ("No devices match these filters"). */
  description?: string;
  /** Call-to-action, e.g. a "Create campaign" button (at most one). */
  action?: ReactNode;
  /** `simple` for inline / table use; `default` (illustration) for pages. */
  variant?: "simple" | "default";
}

/** Consistent empty state (docs/design-system/COMPONENT_CATALOGUE.md) —
 * never a blank area. Reason + optional next action. */
export function EmptyState({ title, description, action, variant = "simple" }: EmptyStateProps) {
  const { token } = theme.useToken();
  return (
    <Empty
      image={variant === "simple" ? Empty.PRESENTED_IMAGE_SIMPLE : Empty.PRESENTED_IMAGE_DEFAULT}
      style={{ marginBlock: token.marginXL }}
      description={
        <>
          <Typography.Text strong style={{ display: "block" }}>
            {title}
          </Typography.Text>
          {description && (
            <Typography.Text type="secondary" style={{ display: "block" }}>
              {description}
            </Typography.Text>
          )}
        </>
      }
    >
      {action}
    </Empty>
  );
}

interface ErrorStateProps {
  title: string;
  description?: string;
  onRetry?: () => void;
}

/** Actionable error state — says what failed and offers a retry; never a
 * raw backend error dump. */
export function ErrorState({ title, description, onRetry }: ErrorStateProps) {
  return (
    <Result
      status="error"
      title={title}
      subTitle={description}
      extra={
        onRetry && (
          <Button type="primary" onClick={onRetry}>
            Retry
          </Button>
        )
      }
    />
  );
}

/** Layout-aware loading: a skeleton for known layouts (first load). Use
 * antd Spin only for in-place refreshes of content already on screen. */
export function LoadingState({ rows = 6 }: { rows?: number }) {
  return <Skeleton active paragraph={{ rows }} aria-busy="true" />;
}
