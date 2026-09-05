import { LockOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { Card, Typography } from "antd";
import type { ReactNode } from "react";
import { EmptyState } from "../../../components/ui/states";
import { ToneTag } from "../../../components/ui/ToneTag";
import type { CalendarEvent } from "../types";
import { formatDayLong } from "./dates";

function Section({
  title,
  icon,
  events,
  renderChip,
  emptyText,
}: {
  title: string;
  icon?: ReactNode;
  events: CalendarEvent[];
  renderChip: (event: CalendarEvent) => ReactNode;
  emptyText?: string;
}) {
  if (events.length === 0 && !emptyText) return null;
  return (
    <section aria-label={title} className="mb-4 last:mb-0">
      <Typography.Text
        type="secondary"
        className="mb-1.5 flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider"
      >
        {icon}
        {title}
        <span className="ml-auto tabular-nums">{events.length || ""}</span>
      </Typography.Text>
      {events.length === 0 ? (
        <Typography.Text type="secondary" className="block text-xs">
          {emptyText}
        </Typography.Text>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {events.map((event) => (
            <li key={`${event.schedule_id}-${event.date}`}>{renderChip(event)}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

/**
 * The selected day, grouped the way an operator asks about it: what is
 * playing now, what is next, what comes later, and the blackouts. Only
 * real events from the calendar response — nothing is synthesised.
 */
export function DayPanel({
  date,
  today,
  nowMinute,
  timezone,
  events,
  renderChip,
  bordered = true,
}: {
  date: string;
  today: string;
  nowMinute: number;
  timezone: string;
  events: CalendarEvent[];
  renderChip: (event: CalendarEvent) => ReactNode;
  bordered?: boolean;
}) {
  const isToday = date === today;
  const isPast = date < today;
  const plays = events.filter((e) => e.kind === "play");
  const blackouts = events.filter((e) => e.kind === "blackout");
  const live = plays.filter((e) => e.live);
  const upcoming = isToday ? plays.filter((e) => !e.live && e.start_minute >= nowMinute) : [];
  const next = upcoming.slice(0, 3);
  const later = upcoming.slice(3);
  const earlier = isToday ? plays.filter((e) => !e.live && e.end_minute <= nowMinute && e.start_minute < nowMinute) : [];
  const conflicts = plays.filter((e) => e.conflict).length;

  const body = (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Typography.Text strong className="text-sm">
          {formatDayLong(date)}
        </Typography.Text>
        {isToday && <ToneTag tone="processing">Today</ToneTag>}
        {conflicts > 0 && (
          <ToneTag tone="error">
            {conflicts} in conflict
          </ToneTag>
        )}
        <Typography.Text type="secondary" className="ml-auto text-xs">
          {timezone}
        </Typography.Text>
      </div>
      {events.length === 0 ? (
        <EmptyState
          title="Nothing scheduled"
          description={isPast ? "No campaign windows ran on this day." : "No campaign windows on this day yet."}
        />
      ) : isToday ? (
        <>
          <Section
            title="Now playing"
            icon={<PlayCircleOutlined aria-hidden />}
            events={live}
            renderChip={renderChip}
            emptyText="No published campaign is in a play window right now."
          />
          <Section title="Next" events={next} renderChip={renderChip} emptyText={upcoming.length ? undefined : "Nothing further today."} />
          <Section title="Later" events={later} renderChip={renderChip} />
          <Section title="Earlier today" events={earlier} renderChip={renderChip} />
          <Section title="Blackouts" icon={<LockOutlined aria-hidden />} events={blackouts} renderChip={renderChip} />
        </>
      ) : (
        <>
          <Section title={isPast ? "Played" : "Scheduled"} events={plays} renderChip={renderChip} />
          <Section title="Blackouts" icon={<LockOutlined aria-hidden />} events={blackouts} renderChip={renderChip} />
        </>
      )}
    </>
  );

  if (!bordered) return <div data-testid="day-panel">{body}</div>;
  return (
    <Card size="small" className="h-full" data-testid="day-panel" styles={{ body: { padding: 12 } }}>
      {body}
    </Card>
  );
}
