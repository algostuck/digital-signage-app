import { Table, type TableProps } from "antd";
import type { ReactNode } from "react";
import { EmptyState, ErrorState } from "./states";

interface DataTableProps<T> extends TableProps<T> {
  /** Error object from the query, if any — renders the standard
   * actionable error state instead of the table. */
  error?: unknown;
  errorTitle?: string;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
}

/** Standard enterprise table (brief §16): one consistent wrapper over
 * antd Table with the app's empty/loading/error contract and compact
 * defaults. Columns/pagination/rowSelection pass straight through. */
export function DataTable<T extends object>({
  error,
  errorTitle = "Unable to load data",
  onRetry,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  emptyAction,
  ...tableProps
}: DataTableProps<T>) {
  if (error) {
    return (
      <ErrorState
        title={errorTitle}
        description="The service did not respond. Your data is safe — try again."
        onRetry={onRetry}
      />
    );
  }
  return (
    <Table<T>
      size="middle"
      scroll={{ x: "max-content" }}
      locale={{
        emptyText: (
          <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
        ),
      }}
      {...tableProps}
    />
  );
}
