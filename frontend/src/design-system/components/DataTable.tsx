import { Flex, Grid, Table, Typography, theme, type TableProps } from "antd";
import type { ReactNode } from "react";
import { formatNumber } from "../utilities/format";
import { EmptyState, ErrorState } from "./states";

export interface DataTableProps<T> extends Omit<TableProps<T>, "size"> {
  /** Error from the query, if any — renders the standard actionable error
   * state instead of the table. */
  error?: unknown;
  errorTitle?: string;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  /** `medium` (default, compact but readable) or `compact` for dense
   * operational tables. */
  density?: "medium" | "compact";
  /** Toolbar shown above the table while rows are selected; announced
   * politely so keyboard and screen-reader users hear the count. */
  bulkActions?: ReactNode;
  /** Below `md`, tapping a row opens its detail instead of showing every
   * column — the mobile strategy of RESPONSIVE_COMPONENT_RULES.md. */
  mobileDetail?: (row: T) => void;
}

/**
 * The enterprise table (docs/design-system/COMPONENT_CATALOGUE.md): one
 * wrapper over antd Table with the app's density, sticky header,
 * horizontal scroll inside the table, pagination defaults, selection
 * toolbar and the shared empty / loading / error contract. Columns follow
 * the alignment rules (text left, numbers right, actions right) — that is
 * the caller's responsibility, documented in DESIGN_SYSTEM_USAGE.md §3.
 */
export function DataTable<T extends object>({
  error,
  errorTitle = "Unable to load data",
  onRetry,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  emptyAction,
  density = "medium",
  bulkActions,
  mobileDetail,
  pagination,
  rowSelection,
  onRow,
  ...tableProps
}: DataTableProps<T>) {
  const { token } = theme.useToken();
  const screens = Grid.useBreakpoint();
  const compactScreen = screens.md === false;

  if (error) {
    return (
      <ErrorState
        title={errorTitle}
        description="The service did not respond. Your data is safe — try again."
        onRetry={onRetry}
      />
    );
  }

  const selectedCount = rowSelection?.selectedRowKeys?.length ?? 0;
  const paginationProps: TableProps<T>["pagination"] =
    pagination === false
      ? false
      : {
          hideOnSinglePage: true,
          showSizeChanger: (pagination?.total ?? 0) > 50,
          showTotal: (total, [from, to]) =>
            `${formatNumber(from)}–${formatNumber(to)} of ${formatNumber(total)}`,
          simple: compactScreen,
          ...pagination,
        };

  return (
    <Flex vertical gap={token.marginSM}>
      {selectedCount > 0 && bulkActions && (
        <Flex
          align="center"
          gap={token.marginSM}
          wrap
          role="region"
          aria-live="polite"
          aria-label="Bulk actions"
          style={{
            padding: `${token.paddingXS}px ${token.paddingSM}px`,
            background: token.colorPrimaryBg,
            borderRadius: token.borderRadius,
          }}
        >
          <Typography.Text strong>{formatNumber(selectedCount)} selected</Typography.Text>
          {bulkActions}
        </Flex>
      )}
      <Table<T>
        size={density === "compact" ? "small" : "medium"}
        sticky
        scroll={{ x: "max-content" }}
        pagination={paginationProps}
        rowSelection={rowSelection}
        onRow={(record, index) => {
          const own = onRow?.(record, index) ?? {};
          if (!compactScreen || !mobileDetail) return own;
          return {
            ...own,
            onClick: (event) => {
              own.onClick?.(event);
              mobileDetail(record);
            },
            style: { cursor: "pointer", ...(own.style ?? {}) },
          };
        }}
        locale={{
          emptyText: (
            <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
          ),
        }}
        {...tableProps}
      />
    </Flex>
  );
}
