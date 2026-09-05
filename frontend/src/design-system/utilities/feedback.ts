import { App } from "antd";
import type { ReactNode } from "react";

/**
 * The feedback vocabulary (docs/design-system/DESIGN_SYSTEM_USAGE.md §12):
 *
 * - `toast`  → antd `message`: immediate confirmation of an action whose
 *   result the user can see (saved, deleted, copied). 3 s, top-centre.
 * - `notify` → antd `notification`: background or system events with
 *   detail (export ready, deployment finished, job failed). Top-right,
 *   stays 6 s, stackable.
 * - `confirm` → antd `modal.confirm`: a decision on a significant or
 *   irreversible action (Popconfirm handles the low-risk inline case via
 *   ConfirmAction).
 *
 * All three go through App.useApp() so they carry the ConfigProvider
 * theme; never import the static `message` / `notification` / `Modal`
 * methods in a module.
 */
export function useFeedback() {
  const { message, notification, modal } = App.useApp();
  return {
    toast: {
      success: (content: ReactNode) => message.success(content),
      error: (content: ReactNode) => message.error(content),
      info: (content: ReactNode) => message.info(content),
      warning: (content: ReactNode) => message.warning(content),
      loading: (content: ReactNode, key?: string) => message.loading({ content, key, duration: 0 }),
      destroy: (key?: string) => message.destroy(key),
    },
    notify: {
      success: (title: ReactNode, description?: ReactNode) =>
        notification.success({ title, description, duration: 6 }),
      error: (title: ReactNode, description?: ReactNode) =>
        notification.error({ title, description, duration: 0 }),
      info: (title: ReactNode, description?: ReactNode) =>
        notification.info({ title, description, duration: 6 }),
      warning: (title: ReactNode, description?: ReactNode) =>
        notification.warning({ title, description, duration: 8 }),
    },
    confirm: (options: {
      title: ReactNode;
      content?: ReactNode;
      okText?: string;
      danger?: boolean;
      onOk: () => void | Promise<void>;
    }) =>
      modal.confirm({
        title: options.title,
        content: options.content,
        okText: options.okText ?? (options.danger ? "Delete" : "Confirm"),
        cancelText: "Cancel",
        okButtonProps: { danger: options.danger },
        onOk: options.onOk,
        centered: true,
      }),
  };
}
