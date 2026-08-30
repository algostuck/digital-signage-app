import { Button, Empty, Result, Skeleton } from "antd";
import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  /** Call-to-action, e.g. a "Create campaign" button. */
  action?: ReactNode;
}

/** Consistent empty state (brief §45) — never a blank screen. */
export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <Empty
      className="my-10"
      description={
        <>
          <p className="font-medium text-slate-700">{title}</p>
          {description && <p className="text-sm text-slate-500">{description}</p>}
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

/** Actionable error state (brief §47) — says what failed and offers a
 * retry; never a raw backend error dump. */
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

/** Layout-aware loading (brief §46): skeleton for known layouts. */
export function LoadingState({ rows = 6 }: { rows?: number }) {
  return <Skeleton active paragraph={{ rows }} aria-busy="true" />;
}
