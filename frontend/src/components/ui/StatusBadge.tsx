import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  InboxOutlined,
  MinusCircleOutlined,
  PauseCircleOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { Tag } from "antd";
import type { ReactNode } from "react";

interface StatusMeta {
  color: string;
  icon: ReactNode;
}

/**
 * Single source of truth for status → color+icon+text across the app.
 * Never communicates state through color alone (brief §26/§35) — every
 * status carries an icon and its own text label too.
 */
const STATUS_META: Record<string, StatusMeta> = {
  active: { color: "success", icon: <CheckCircleOutlined /> },
  online: { color: "success", icon: <CheckCircleOutlined /> },
  ready: { color: "success", icon: <CheckCircleOutlined /> },
  published: { color: "success", icon: <CheckCircleOutlined /> },
  approved: { color: "success", icon: <CheckCircleOutlined /> },
  acknowledged: { color: "success", icon: <CheckCircleOutlined /> },
  confirmed: { color: "success", icon: <CheckCircleOutlined /> },
  completed: { color: "success", icon: <CheckCircleOutlined /> },

  invited: { color: "warning", icon: <ClockCircleOutlined /> },
  warning: { color: "warning", icon: <ExclamationCircleOutlined /> },
  pending: { color: "warning", icon: <ClockCircleOutlined /> },
  pending_approval: { color: "warning", icon: <ClockCircleOutlined /> },
  paused: { color: "warning", icon: <PauseCircleOutlined /> },
  partial: { color: "warning", icon: <ExclamationCircleOutlined /> },
  stale: { color: "warning", icon: <ExclamationCircleOutlined /> },
  degraded: { color: "warning", icon: <ExclamationCircleOutlined /> },
  flagged: { color: "warning", icon: <ExclamationCircleOutlined /> },

  publishing: { color: "processing", icon: <SyncOutlined spin /> },
  processing: { color: "processing", icon: <SyncOutlined spin /> },
  syncing: { color: "processing", icon: <SyncOutlined spin /> },
  updating: { color: "processing", icon: <SyncOutlined spin /> },
  running: { color: "processing", icon: <SyncOutlined spin /> },

  offline: { color: "error", icon: <CloseCircleOutlined /> },
  critical: { color: "error", icon: <CloseCircleOutlined /> },
  rejected: { color: "error", icon: <CloseCircleOutlined /> },
  failed: { color: "error", icon: <CloseCircleOutlined /> },
  error: { color: "error", icon: <CloseCircleOutlined /> },
  suspended: { color: "error", icon: <CloseCircleOutlined /> },

  deactivated: { color: "default", icon: <MinusCircleOutlined /> },
  disabled: { color: "default", icon: <MinusCircleOutlined /> },
  decommissioned: { color: "default", icon: <MinusCircleOutlined /> },
  draft: { color: "default", icon: <EditOutlined /> },
  archived: { color: "default", icon: <InboxOutlined /> },
  expired: { color: "default", icon: <MinusCircleOutlined /> },
  queued: { color: "default", icon: <ClockCircleOutlined /> },
  cancelled: { color: "default", icon: <MinusCircleOutlined /> },
  resolved: { color: "default", icon: <CheckCircleOutlined /> },
};

function toLabel(status: string): string {
  return status
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? { color: "default", icon: <MinusCircleOutlined /> };
  return (
    <Tag color={meta.color} icon={meta.icon} variant="filled">
      {toLabel(status)}
    </Tag>
  );
}
