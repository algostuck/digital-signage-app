import { Flex, Listy, Skeleton, Typography, theme } from "antd";
import type { CSSProperties, ReactNode } from "react";
import { EmptyState, ErrorState } from "./states";

export interface EntityListProps<T> {
  items: T[] | undefined;
  rowKey: keyof T | ((item: T) => React.Key);
  /** Row content; use `EntityList.Row` for the standard title / meta /
   * actions arrangement. */
  renderItem: (item: T, index: number) => ReactNode;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  /** Virtualise long lists (> ~100 rows); requires `height`. */
  virtual?: boolean;
  height?: number;
  /** Group rows under sticky headers (by date, severity…). */
  group?: { getKey: (item: T) => React.Key; render: (key: React.Key, items: T[]) => ReactNode };
  /** Draw a divider between rows (default true). */
  split?: boolean;
  /** Tighter row padding for dense panels. */
  dense?: boolean;
  header?: ReactNode;
  footer?: ReactNode;
  className?: string;
  style?: CSSProperties;
  "aria-label"?: string;
}

/**
 * List-shaped content (docs/design-system/COMPONENT_CATALOGUE.md):
 * activity, notifications, approvals, queues, agendas — on antd Listy
 * (the List replacement in antd 6.6) with the shared loading / empty /
 * error contract, optional virtualisation and sticky group headers.
 */
export function EntityList<T>({
  items,
  rowKey,
  renderItem,
  loading,
  error,
  onRetry,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  emptyAction,
  virtual,
  height,
  group,
  split = true,
  dense,
  header,
  footer,
  className,
  style,
  "aria-label": ariaLabel,
}: EntityListProps<T>) {
  const { token } = theme.useToken();
  if (error) {
    return <ErrorState title="Unable to load this list" description="Your data is safe — try again." onRetry={onRetry} />;
  }
  if (loading && !items) {
    return <Skeleton active paragraph={{ rows: 4 }} aria-busy="true" />;
  }
  if (!items || items.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />;
  }
  return (
    <Flex vertical gap={0} role="list" aria-label={ariaLabel} aria-busy={loading || undefined} className={className} style={style}>
      {header}
      <Listy<T>
        items={items}
        rowKey={rowKey as never}
        virtual={virtual}
        height={height}
        sticky={Boolean(group)}
        group={group ? { key: group.getKey, title: group.render } : undefined}
        itemRender={(item, index) => (
          <div
            role="listitem"
            style={{
              paddingBlock: dense ? token.paddingXS : token.paddingSM,
              borderBottom: split && index < items.length - 1 ? `1px solid ${token.colorBorderSecondary}` : undefined,
            }}
          >
            {renderItem(item, index)}
          </div>
        )}
      />
      {footer}
    </Flex>
  );
}

/** Standard row: leading (avatar / icon), title + meta, trailing actions. */
function Row({
  leading,
  title,
  meta,
  actions,
  muted,
}: {
  leading?: ReactNode;
  title: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  /** Read / inactive rows. */
  muted?: boolean;
}) {
  const { token } = theme.useToken();
  return (
    <Flex align="center" gap={token.marginSM} wrap style={{ opacity: muted ? 0.65 : 1 }}>
      {leading && <span style={{ flexShrink: 0, display: "inline-flex" }}>{leading}</span>}
      <Flex vertical style={{ minWidth: 0, flex: 1 }}>
        <Typography.Text strong={!muted} ellipsis style={{ display: "block" }}>
          {title}
        </Typography.Text>
        {meta && (
          <Typography.Text type="secondary" style={{ fontSize: token.fontSizeSM }}>
            {meta}
          </Typography.Text>
        )}
      </Flex>
      {actions && <Flex gap={token.marginXXS} wrap style={{ flexShrink: 0 }}>{actions}</Flex>}
    </Flex>
  );
}

EntityList.Row = Row;
