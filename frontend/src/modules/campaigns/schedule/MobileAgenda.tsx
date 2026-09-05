import { Card } from "antd";
import type { ReactNode } from "react";
import { useEffect, useRef } from "react";
import type { CalendarEvent } from "../types";
import { DayPanel } from "./DayPanel";
import { dayNumber, weekdayShort } from "./dates";

/**
 * Phones get a date strip and an agenda, never a seven-column grid. The
 * strip scrolls horizontally inside its own container; the agenda is the
 * same day panel the desktop shows beside the calendar.
 */
export function MobileAgenda({
  days,
  selectedDate,
  today,
  nowMinute,
  timezone,
  eventsByDate,
  onSelectDate,
  renderChip,
}: {
  days: string[];
  selectedDate: string;
  today: string;
  nowMinute: number;
  timezone: string;
  eventsByDate: Map<string, CalendarEvent[]>;
  onSelectDate: (iso: string) => void;
  renderChip: (event: CalendarEvent) => ReactNode;
}) {
  const stripRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    stripRef.current
      ?.querySelector<HTMLElement>(`[data-day="${selectedDate}"]`)
      ?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [selectedDate]);

  return (
    <div data-testid="mobile-agenda">
      <div
        ref={stripRef}
        role="tablist"
        aria-label="Days"
        className="mb-3 flex gap-1 overflow-x-auto pb-1"
        style={{ scrollbarWidth: "thin" }}
      >
        {days.map((iso) => {
          const events = eventsByDate.get(iso) ?? [];
          const conflicts = events.some((e) => e.conflict);
          const selected = iso === selectedDate;
          return (
            <button
              key={iso}
              type="button"
              role="tab"
              aria-selected={selected}
              data-day={iso}
              onClick={() => onSelectDate(iso)}
              aria-label={`${weekdayShort(iso)} ${dayNumber(iso)}${iso === today ? ", today" : ""}, ${events.length} windows${
                conflicts ? ", conflicts" : ""
              }`}
              className={`flex min-w-14 shrink-0 flex-col items-center rounded-lg border px-2 py-1.5 text-xs focus-visible:ring-2 ${
                selected ? "border-current font-semibold" : "border-transparent"
              }`}
            >
              <span className="uppercase opacity-70">{weekdayShort(iso)}</span>
              <span className={`text-base ${iso === today ? "underline decoration-2 underline-offset-4" : ""}`}>
                {dayNumber(iso)}
              </span>
              <span className="mt-0.5 flex h-1.5 gap-0.5" aria-hidden>
                {events.slice(0, 3).map((e) => (
                  <span
                    key={`${e.schedule_id}-${e.date}`}
                    className={`h-1.5 w-1.5 rounded-full ${e.conflict ? "bg-red-600" : "bg-current opacity-50"}`}
                  />
                ))}
              </span>
            </button>
          );
        })}
      </div>
      <Card size="small" styles={{ body: { padding: 12 } }}>
        <DayPanel
          date={selectedDate}
          today={today}
          nowMinute={nowMinute}
          timezone={timezone}
          events={eventsByDate.get(selectedDate) ?? []}
          renderChip={renderChip}
          bordered={false}
        />
      </Card>
    </div>
  );
}
