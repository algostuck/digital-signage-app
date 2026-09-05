import { Calendar, Popover, Typography } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import type { ReactNode } from "react";
import type { CalendarEvent } from "../types";
import { formatDayLong } from "./dates";

const MAX_CHIPS = 3;

/**
 * Month view on Ant Design's Calendar: our header drives navigation (so
 * the antd header is hidden), every date cell shows up to three compact
 * chips and a "+N more" popover, and selecting a date feeds the day
 * panel. Cells outside the anchored month are dimmed by antd itself.
 */
export function MonthView({
  anchor,
  selectedDate,
  today,
  eventsByDate,
  onSelectDate,
  renderChip,
}: {
  anchor: string;
  selectedDate: string;
  today: string;
  eventsByDate: Map<string, CalendarEvent[]>;
  onSelectDate: (iso: string) => void;
  renderChip: (event: CalendarEvent, compact: boolean) => ReactNode;
}) {
  const value = dayjs(selectedDate.slice(0, 7) === anchor.slice(0, 7) ? selectedDate : anchor);

  const cellRender = (date: Dayjs, info: { type: string; originNode: ReactNode }) => {
    if (info.type !== "date") return info.originNode;
    const iso = date.format("YYYY-MM-DD");
    const events = eventsByDate.get(iso) ?? [];
    if (events.length === 0) return null;
    const shown = events.slice(0, MAX_CHIPS);
    const hidden = events.length - shown.length;
    const conflicts = events.filter((e) => e.conflict).length;
    return (
      <div className="flex flex-col gap-0.5" data-testid={`month-cell-${iso}`}>
        {iso === today && <span className="sr-only">Today.</span>}
        {shown.map((event) => (
          <div key={`${event.schedule_id}-${event.date}`}>{renderChip(event, true)}</div>
        ))}
        {hidden > 0 && (
          <Popover
            trigger={["click"]}
            placement="rightTop"
            title={
              <span>
                {formatDayLong(iso)} · {events.length} windows
                {conflicts ? ` · ${conflicts} in conflict` : ""}
              </span>
            }
            content={
              <div className="flex max-h-72 w-64 flex-col gap-1 overflow-y-auto">
                {events.map((event) => (
                  <div key={`${event.schedule_id}-${event.date}-all`}>{renderChip(event, false)}</div>
                ))}
              </div>
            }
          >
            <button
              type="button"
              className="w-full rounded-sm px-1 text-left text-xs font-medium underline-offset-2 hover:underline focus-visible:ring-2"
              aria-label={`${hidden} more windows on ${formatDayLong(iso)}`}
              onClick={(e) => e.stopPropagation()}
            >
              +{hidden} more
            </button>
          </Popover>
        )}
      </div>
    );
  };

  return (
    <div className="schedule-month" data-testid="month-view">
      <Calendar
        value={value}
        headerRender={() => null}
        cellRender={cellRender}
        onSelect={(date, { source }) => {
          if (source === "date") onSelectDate(date.format("YYYY-MM-DD"));
        }}
      />
      <Typography.Text type="secondary" className="mt-2 block text-xs">
        Up to three windows per day are shown; “+N more” lists the rest. Select a day to see its
        full timeline.
      </Typography.Text>
    </div>
  );
}
