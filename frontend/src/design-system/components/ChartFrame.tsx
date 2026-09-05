import { Card, Skeleton, Typography, theme } from "antd";
import type { ReactNode } from "react";
import { HEADING } from "../tokens/scale";
import { EmptyState, ErrorState } from "./states";

interface ChartFrameProps {
  title: ReactNode;
  /** Right-hand slot — a "View all" link, a range Segmented. */
  extra?: ReactNode;
  /** One sentence stating what the visual shows, in words. Rendered as
   * secondary text and available to assistive tech, so nothing is
   * conveyed only by a picture. */
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
  id?: string;
}

/**
 * The container for every chart and dashboard panel
 * (docs/design-system/COMPONENT_CATALOGUE.md): Card + level-5 title +
 * summary + one loading / empty / error contract, so panels degrade
 * independently and read the same everywhere.
 */
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
  const { token } = theme.useToken();
  let body: ReactNode;
  if (error) {
    body = (
      <ErrorState
        title="Unable to load this section"
        description="The rest of the page is unaffected."
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
      title={<Typography.Title level={HEADING.card}>{title}</Typography.Title>}
      extra={extra}
      style={{ height: "100%" }}
      styles={{ body: { minHeight } }}
    >
      {summary && !loading && !error && !empty && (
        <Typography.Paragraph type="secondary" style={{ marginBottom: token.marginSM, fontSize: token.fontSizeSM }}>
          {summary}
        </Typography.Paragraph>
      )}
      {body}
    </Card>
  );
}
