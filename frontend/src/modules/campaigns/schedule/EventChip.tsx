import {
  ClockCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  EnvironmentOutlined,
  ExportOutlined,
  LockOutlined,
  PlayCircleOutlined,
  RetweetOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Button, Popconfirm, Popover, Space, Typography } from "antd";
import { forwardRef, type ButtonHTMLAttributes, type CSSProperties, type ReactNode } from "react";
import { ToneTag } from "../../../components/ui/ToneTag";
import { useThemeMode } from "../../../theme/ThemeProvider";
import type { CalendarEvent, ScheduleConflict } from "../types";
import { durationLabel, windowLabel } from "./dates";
import {
  blackoutStyle,
  campaignStyle,
  REASON_LABEL,
  SEVERITY_LABEL,
  severityTone,
  statusLabel,
  statusTone,
} from "./palette";

export interface EventActions {
  onOpenCampaign: (campaignId: string) => void;
  onEdit?: (event: CalendarEvent) => void;
  onDelete?: (event: CalendarEvent) => void;
  onShowConflict?: (conflict: ScheduleConflict) => void;
}

/** The accessible name: everything the colour and icons say, in words. */
export function eventLabel(event: CalendarEvent): string {
  const parts = [
    event.campaign_name,
    windowLabel(event.start_minute, event.end_minute, event.overnight),
    event.kind === "blackout" ? "blackout" : statusLabel(event.campaign_status),
  ];
  if (event.live) parts.push("playing now");
  if (event.conflict) parts.push("conflict");
  if (event.recurrence_type !== "daily" && event.recurrence_type !== "once") parts.push("recurring");
  return parts.join(", ");
}

export function eventStyle(event: CalendarEvent, mode: "light" | "dark"): CSSProperties {
  const base = event.kind === "blackout" ? blackoutStyle(mode) : campaignStyle(event.campaign_id, mode);
  const muted =
    event.kind !== "blackout" &&
    (event.expired || event.campaign_status === "expired" || event.campaign_status === "archived");
  return {
    ...base,
    opacity: muted ? 0.6 : 1,
    outline: event.conflict ? "2px dashed currentColor" : undefined,
    outlineOffset: event.conflict ? -2 : undefined,
  };
}

/** The conflict from *this* window's point of view: the shadowed side
 * "never plays", the covering side "covers", a blackout "suppresses". */
export function conflictLine(conflict: ScheduleConflict, event: CalendarEvent): string {
  const [first, second] = conflict.campaigns;
  const mine = first.schedule_id === event.schedule_id ? first : second;
  const other = mine === first ? second : first;
  const otherName = other.campaign_name;
  if (conflict.reason === "equal_priority_shared_screens") {
    return `${REASON_LABEL[conflict.reason]} with ${otherName}${
      conflict.winner_campaign_id === mine.campaign_id ? " (this one wins the tie-break)" : ""
    }`;
  }
  if (conflict.reason === "shadowed_by_priority") {
    return mine === first
      ? `Never plays — fully covered by ${otherName} (priority ${other.campaign_priority})`
      : `Covers ${otherName}, which never plays on the shared screens`;
  }
  return mine === first
    ? "Sits inside the campaign's own blackout, so it never plays"
    : `Suppresses ${other.schedule_name ?? "a play window"} entirely`;
}

export function EventIcons({ event }: { event: CalendarEvent }) {
  return (
    <span className="inline-flex shrink-0 items-center gap-1">
      {event.kind === "blackout" && <LockOutlined aria-hidden />}
      {event.live && <PlayCircleOutlined aria-hidden />}
      {event.conflict && <WarningOutlined aria-hidden />}
      {event.recurrence_type === "weekly" || event.recurrence_type === "monthly" ? (
        <RetweetOutlined aria-hidden />
      ) : null}
    </span>
  );
}

/** Rich hover / focus card for any event chip or block. */
export function EventPopover({
  event,
  conflicts,
  actions,
  canManage,
  children,
}: {
  event: CalendarEvent;
  conflicts: ScheduleConflict[];
  actions: EventActions;
  canManage: boolean;
  children: ReactNode;
}) {
  const { mode } = useThemeMode();
  const swatch = eventStyle(event, mode);
  const content = (
    <div className="max-w-xs">
      <div className="mb-2 flex items-start gap-2">
        <span
          aria-hidden
          className="mt-1 inline-block h-3 w-3 shrink-0 rounded-sm"
          style={{ background: swatch.borderLeft?.toString().split(" ").pop() }}
        />
        <div className="min-w-0">
          <Typography.Text strong className="block leading-snug">
            {event.campaign_name}
          </Typography.Text>
          {event.schedule_name && (
            <Typography.Text type="secondary" className="block text-xs">
              {event.schedule_name}
            </Typography.Text>
          )}
        </div>
      </div>
      <Space size={4} wrap className="mb-2">
        {event.kind === "blackout" ? (
          <ToneTag tone="default" icon={<LockOutlined />}>
            Blackout
          </ToneTag>
        ) : (
          <ToneTag tone={statusTone(event.campaign_status)}>{statusLabel(event.campaign_status)}</ToneTag>
        )}
        {event.live && (
          <ToneTag tone="success" icon={<PlayCircleOutlined />}>
            Playing now
          </ToneTag>
        )}
        {event.expired && <ToneTag tone="default">Window ended</ToneTag>}
      </Space>
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="m-0 opacity-70">
          <ClockCircleOutlined aria-hidden /> Time
        </dt>
        <dd className="m-0">
          {windowLabel(event.start_minute, event.end_minute, event.overnight)} ·{" "}
          {durationLabel(event.start_minute, event.end_minute)}
          {event.timezone ? ` · ${event.timezone}` : ""}
        </dd>
        <dt className="m-0 opacity-70">
          <RetweetOutlined aria-hidden /> Repeats
        </dt>
        <dd className="m-0">{event.recurrence_text || "Every day"}</dd>
        <dt className="m-0 opacity-70">
          <EnvironmentOutlined aria-hidden /> Reach
        </dt>
        <dd className="m-0">
          {event.screens === 0
            ? "No active screens targeted"
            : `${event.screens} screen${event.screens === 1 ? "" : "s"} in ${event.locations} location${
                event.locations === 1 ? "" : "s"
              }`}
        </dd>
        <dt className="m-0 opacity-70">Priority</dt>
        <dd className="m-0">
          campaign {event.campaign_priority} · window {event.priority}
        </dd>
      </dl>
      {conflicts.length > 0 && (
        <div className="mt-2 border-t border-current/10 pt-2">
          <Typography.Text strong className="block text-xs">
            Conflicts
          </Typography.Text>
          <ul className="m-0 list-none space-y-1 p-0 text-xs">
            {conflicts.map((conflict) => {
              return (
                <li key={conflict.id} className="flex flex-wrap items-center gap-1">
                  <ToneTag tone={severityTone(conflict.severity)} className="!mr-0">
                    {SEVERITY_LABEL[conflict.severity]}
                  </ToneTag>
                  <span>{conflictLine(conflict, event)}</span>
                  {actions.onShowConflict && (
                    <Button
                      type="link"
                      size="small"
                      className="!h-auto !p-0"
                      onClick={() => actions.onShowConflict?.(conflict)}
                    >
                      Review
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-1">
        <Button
          size="small"
          icon={<ExportOutlined />}
          onClick={() => actions.onOpenCampaign(event.campaign_id)}
        >
          Open campaign
        </Button>
        {canManage && actions.onEdit && (
          <Button size="small" icon={<EditOutlined />} onClick={() => actions.onEdit?.(event)}>
            Edit window
          </Button>
        )}
        {canManage && actions.onDelete && (
          <Popconfirm
            title="Delete this schedule window?"
            description="Every occurrence of this window is removed."
            okButtonProps={{ danger: true }}
            onConfirm={() => actions.onDelete?.(event)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Delete
            </Button>
          </Popconfirm>
        )}
      </div>
    </div>
  );
  return (
    <Popover content={content} trigger={["hover", "focus"]} mouseEnterDelay={0.25} placement="right">
      {children}
    </Popover>
  );
}

interface EventChipProps {
  event: CalendarEvent;
  compact?: boolean;
  selected?: boolean;
  onClick?: () => void;
  className?: string;
}

/** Compact chip for month cells, agenda rows and the mobile list. Forwards
 * its ref (and the Popover trigger handlers) so it can sit inside a Popover. */
export const EventChip = forwardRef<
  HTMLButtonElement,
  EventChipProps & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick" | "className">
>(
  function EventChip({ event, compact = false, selected = false, onClick, className = "", ...triggerProps }, ref) {
  const { mode } = useThemeMode();
  return (
    <button
      {...triggerProps}
      ref={ref}
      type="button"
      aria-label={eventLabel(event)}
      aria-pressed={selected || undefined}
      onClick={onClick}
      className={`flex w-full items-center gap-1 rounded-sm px-1.5 text-left text-xs leading-5 transition-shadow focus-visible:ring-2 focus-visible:ring-offset-1 ${
        compact ? "truncate" : "py-0.5"
      } ${className}`}
      style={eventStyle(event, mode)}
    >
      <span className="shrink-0 tabular-nums opacity-80">
        {windowLabel(event.start_minute, event.end_minute).split("–")[0]}
      </span>
      <span className="min-w-0 flex-1 truncate font-medium">{event.campaign_name}</span>
      <EventIcons event={event} />
    </button>
  );
  },
);
