import { Card, Skeleton, Typography } from "antd";
import type { ReactNode } from "react";
import { EmptyState, ErrorState } from "@/design-system";

interface ChartFrameProps {
  title: ReactNode;
  /** Right-hand slot — usually a "View all" link. */
  extra?: ReactNode;
  /** One sentence stating what the visual shows, in words. Rendered as
   * secondary text and available to assistive tech, so nothing on the
   * dashboard is conveyed only by a picture. */
  summary?: ReactNode;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  empty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  minHeight?: number;
  children: ReactNode;
  /** Section heading level for the card title (h2 by default). */
  id?: string;
}

/** Every dashboard widget renders through this so all of them share one
 * loading / empty / error contract and degrade independently. */
export function ChartFrame({
  title,
  extra,
  summary,
  loading,
  error,
  onRetry,
  empty,
  emptyTitle = "Nothing to show yet",
  emptyDescription,
  emptyAction,
  minHeight,
  children,
  id,
}: ChartFrameProps) {
  let body: ReactNode;
  if (error) {
    body = (
      <ErrorState
        title="Unable to load this section"
        description="The rest of the dashboard is unaffected."
        onRetry={onRetry}
      />
    );
  } else if (loading) {
    body = <Skeleton active paragraph={{ rows: 4 }} />;
  } else if (empty) {
    body = <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />;
  } else {
    body = children;
  }

  return (
    <Card
      size="small"
      id={id}
      title={
        <Typography.Text strong className="text-[15px]">
          {title}
        </Typography.Text>
      }
      extra={extra}
      className="h-full"
      styles={{ body: { minHeight } }}
    >
      {summary && !loading && !error && !empty && (
        <Typography.Paragraph type="secondary" className="!mb-3 text-[13px]">
          {summary}
        </Typography.Paragraph>
      )}
      {body}
    </Card>
  );
}
