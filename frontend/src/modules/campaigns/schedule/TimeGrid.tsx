import { Popover, theme, Typography } from "antd";
import { useEffect, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from "react";
import { useThemeMode } from "../../../theme/ThemeProvider";
import type { CalendarEvent } from "../types";
import { addDays, DAY_MINUTES, dayNumber, minuteLabel, weekdayShort, windowLabel } from "./dates";
import { EventIcons, eventLabel, eventStyle } from "./EventChip";

export const HOUR_PX = 48;
const GRID_HEIGHT = HOUR_PX * 24;
const SNAP_MINUTES = 15;
const DRAG_THRESHOLD_PX = 4;

interface Placed {
  event: CalendarEvent;
  lane: number;
  lanes: number;
  cluster: number;
}

interface Cluster {
  index: number;
  start: number;
  end: number;
  events: CalendarEvent[];
  hidden: number;
}

/** Interval partitioning: overlapping windows share a cluster and get a
 * lane each, so a three-way overlap renders as three side-by-side blocks
 * rather than a stack. Pure, so it is easy to reason about. */
export function layoutDay(events: CalendarEvent[]): Placed[] {
  const sorted = [...events].sort(
    (a, b) =>
      a.start_minute - b.start_minute ||
      b.end_minute - b.start_minute - (a.end_minute - a.start_minute) ||
      a.campaign_name.localeCompare(b.campaign_name),
  );
  const placed: Placed[] = [];
  let cluster: Placed[] = [];
  let laneEnds: number[] = [];
  let clusterEnd = -1;
  let clusterIndex = 0;
  const flush = () => {
    const lanes = laneEnds.length;
    for (const item of cluster) item.lanes = lanes;
    placed.push(...cluster);
    cluster = [];
    laneEnds = [];
    clusterIndex += 1;
  };
  for (const event of sorted) {
    if (cluster.length && event.start_minute >= clusterEnd) flush();
    let lane = laneEnds.findIndex((end) => end <= event.start_minute);
    if (lane === -1) {
      lane = laneEnds.length;
      laneEnds.push(event.end_minute);
    } else {
      laneEnds[lane] = event.end_minute;
    }
    cluster.push({ event, lane, lanes: 0, cluster: clusterIndex });
    clusterEnd = Math.max(clusterEnd, event.end_minute);
  }
  flush();
  return placed;
}

/** Dense days (the seeded estate has ~30 windows a day) would become
 * unreadable slivers; beyond `maxLanes` the rest of a cluster collapses
 * into one "+N" chip that lists them. */
export function clustersOf(placed: Placed[], maxLanes: number): Cluster[] {
  const map = new Map<number, Cluster>();
  for (const item of placed) {
    const cluster = map.get(item.cluster) ?? {
      index: item.cluster,
      start: item.event.start_minute,
      end: item.event.end_minute,
      events: [],
      hidden: 0,
    };
    cluster.start = Math.min(cluster.start, item.event.start_minute);
    cluster.end = Math.max(cluster.end, item.event.end_minute);
    cluster.events.push(item.event);
    if (item.lane >= maxLanes) cluster.hidden += 1;
    map.set(item.cluster, cluster);
  }
  return [...map.values()];
}

export interface MoveProposal {
  event: CalendarEvent;
  date: string;
  start_minute: number;
  end_minute: number;
}

interface DragState {
  event: CalendarEvent;
  originX: number;
  originY: number;
  dx: number;
  dy: number;
}

/**
 * Week and day views: a 24-hour grid, one column per day, events as
 * blocks spanning their duration, a current-time line in today's column,
 * click-to-schedule on empty slots and drag-to-move (snapped to 15 min)
 * that hands a *proposal* back — nothing moves until the caller confirms
 * it against the conflict dry-run and the API accepts the change.
 */
export function TimeGrid({
  days,
  eventsByDate,
  today,
  nowMinute,
  selectedDate,
  onSelectDate,
  onSlotClick,
  onMove,
  canManage,
  renderBlock,
  renderChip,
}: {
  days: string[];
  eventsByDate: Map<string, CalendarEvent[]>;
  today: string;
  nowMinute: number;
  selectedDate: string;
  onSelectDate: (iso: string) => void;
  onSlotClick?: (iso: string, minute: number) => void;
  onMove?: (proposal: MoveProposal) => void;
  canManage: boolean;
  /** Wraps a block (a focusable button) with its popover. */
  renderBlock: (event: CalendarEvent, button: ReactNode) => ReactNode;
  /** Chip renderer for the "+N" overflow list. */
  renderChip: (event: CalendarEvent) => ReactNode;
}) {
  const { token } = theme.useToken();
  const { mode } = useThemeMode();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const columnWidthRef = useRef(160);
  // Lanes per column follow the real column width so blocks stay legible:
  // ~60 px per lane in week view, ~90 px in day view.
  const [columnWidth, setColumnWidth] = useState(160);
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      const column = el.querySelector<HTMLElement>("[data-day-column]");
      if (column) setColumnWidth(column.getBoundingClientRect().width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [days.length]);
  const maxLanes =
    days.length === 1
      ? Math.min(8, Math.max(2, Math.floor(columnWidth / 90)))
      : Math.min(4, Math.max(1, Math.floor(columnWidth / 60)));

  // First paint: scroll to an hour before now (today) or to 08:00.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const target = days.includes(today) ? Math.max(0, nowMinute - 60) : 8 * 60;
    el.scrollTop = (target / DAY_MINUTES) * GRID_HEIGHT;
    // Only on mount / when the visible days change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days.join(",")]);

  const measureColumn = (el: HTMLElement) => {
    const column = el.closest<HTMLElement>("[data-day-column]");
    if (column) columnWidthRef.current = column.getBoundingClientRect().width;
  };

  const snapped = (state: DragState) => {
    const deltaMinutes = Math.round(((state.dy / GRID_HEIGHT) * DAY_MINUTES) / SNAP_MINUTES) * SNAP_MINUTES;
    const deltaDays = days.length > 1 ? Math.round(state.dx / columnWidthRef.current) : 0;
    return { deltaMinutes, deltaDays };
  };

  const draggable = (event: CalendarEvent) =>
    canManage && !!onMove && event.kind !== "blackout" && !event.expired && !event.overnight;

  const handlePointerDown = (event: CalendarEvent) => (e: PointerEvent<HTMLButtonElement>) => {
    if (!draggable(event) || e.button !== 0) return;
    measureColumn(e.currentTarget);
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      // Synthetic or already-released pointers: dragging still works via bubbling.
    }
    setDrag({ event, originX: e.clientX, originY: e.clientY, dx: 0, dy: 0 });
  };
  const handlePointerMove = (e: PointerEvent<HTMLButtonElement>) => {
    if (!drag) return;
    setDrag({ ...drag, dx: e.clientX - drag.originX, dy: e.clientY - drag.originY });
  };
  const handlePointerUp = (e: PointerEvent<HTMLButtonElement>) => {
    if (!drag) return;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // Nothing captured.
    }
    const state = drag;
    setDrag(null);
    if (Math.abs(state.dx) < DRAG_THRESHOLD_PX && Math.abs(state.dy) < DRAG_THRESHOLD_PX) {
      onSelectDate(state.event.date);
      return;
    }
    const { deltaMinutes, deltaDays } = snapped(state);
    if (deltaMinutes === 0 && deltaDays === 0) return;
    const start = state.event.start_minute + deltaMinutes;
    const end = state.event.end_minute + deltaMinutes;
    if (start < 0 || end > DAY_MINUTES || start >= end) return;
    onMove?.({
      event: state.event,
      date: addDays(state.event.date, deltaDays),
      start_minute: start,
      end_minute: end,
    });
  };

  const lineColor = token.colorBorderSecondary;
  const columnStyle: CSSProperties = {
    height: GRID_HEIGHT,
    backgroundImage: `repeating-linear-gradient(to bottom, ${lineColor} 0 1px, transparent 1px ${HOUR_PX}px)`,
  };
  const dragPreview = drag ? snapped(drag) : null;

  return (
    <div
      ref={scrollRef}
      className="relative max-h-[68vh] overflow-auto rounded-lg border"
      style={{ borderColor: token.colorBorderSecondary, background: token.colorBgContainer }}
      data-testid="time-grid"
    >
      <div
        className="grid"
        style={{
          gridTemplateColumns: `56px repeat(${days.length}, minmax(${days.length === 1 ? 240 : 120}px, 1fr))`,
        }}
        role="grid"
        aria-label={days.length === 1 ? "Day timeline" : "Week timeline"}
      >
        {/* Sticky header row */}
        <div
          className="sticky top-0 z-20 border-b"
          style={{ background: token.colorBgContainer, borderColor: lineColor }}
          role="columnheader"
          aria-label="Time"
        />
        {days.map((iso) => {
          const isToday = iso === today;
          const isSelected = iso === selectedDate;
          const count = eventsByDate.get(iso)?.length ?? 0;
          return (
            <div
              key={iso}
              role="columnheader"
              className="sticky top-0 z-20 border-b border-l px-2 py-1.5"
              style={{ background: token.colorBgContainer, borderColor: lineColor }}
            >
              <button
                type="button"
                onClick={() => onSelectDate(iso)}
                aria-pressed={isSelected}
                aria-label={`${weekdayShort(iso)} ${dayNumber(iso)}${isToday ? ", today" : ""}, ${count} windows`}
                className="flex w-full items-baseline gap-1.5 rounded-sm text-left focus-visible:ring-2"
              >
                <span className="text-xs uppercase tracking-wide opacity-70">{weekdayShort(iso)}</span>
                <span
                  className={`inline-flex h-7 min-w-7 items-center justify-center rounded-full px-1 text-sm font-semibold ${
                    isToday ? "text-white" : ""
                  }`}
                  style={{
                    background: isToday ? token.colorPrimary : isSelected ? token.colorFillSecondary : undefined,
                  }}
                >
                  {dayNumber(iso)}
                </span>
                {count > 0 && (
                  <span className="ml-auto text-xs tabular-nums opacity-70" aria-hidden>
                    {count}
                  </span>
                )}
              </button>
            </div>
          );
        })}

        {/* Time gutter */}
        <div className="sticky left-0 z-10 select-none" style={{ ...columnStyle, background: token.colorBgContainer }}>
          {Array.from({ length: 24 }, (_, hour) => (
            <div
              key={hour}
              className="pr-1.5 text-right text-[11px] tabular-nums opacity-70"
              style={{ height: HOUR_PX, transform: "translateY(-7px)" }}
              aria-hidden
            >
              {hour === 0 ? "" : minuteLabel(hour * 60)}
            </div>
          ))}
        </div>

        {/* Day columns */}
        {days.map((iso) => {
          const placed = layoutDay(eventsByDate.get(iso) ?? []);
          const clusters = clustersOf(placed, maxLanes).filter((c) => c.hidden > 0);
          const isToday = iso === today;
          return (
            <div
              key={iso}
              role="gridcell"
              data-day-column={iso}
              className={`relative border-l ${canManage && onSlotClick ? "cursor-cell" : ""}`}
              style={{
                ...columnStyle,
                borderColor: lineColor,
                background: iso === selectedDate && days.length > 1 ? token.colorFillQuaternary : undefined,
              }}
              onClick={(e) => {
                if (!onSlotClick || !canManage || e.target !== e.currentTarget) return;
                const rect = e.currentTarget.getBoundingClientRect();
                const minute = ((e.clientY - rect.top) / GRID_HEIGHT) * DAY_MINUTES;
                onSlotClick(iso, Math.floor(minute / 30) * 30);
              }}
            >
              {placed.map(({ event, lane, lanes }) => {
                if (lane >= maxLanes) return null;
                const visibleLanes = Math.min(lanes, maxLanes);
                const isDragging = drag?.event === event;
                const duration = event.end_minute - event.start_minute;
                const top = (event.start_minute / DAY_MINUTES) * GRID_HEIGHT;
                const height = Math.max((duration / DAY_MINUTES) * GRID_HEIGHT, 20);
                const shift =
                  isDragging && dragPreview
                    ? `translate(${dragPreview.deltaDays * columnWidthRef.current}px, ${
                        (dragPreview.deltaMinutes / DAY_MINUTES) * GRID_HEIGHT
                      }px)`
                    : undefined;
                const button = (
                  <button
                    type="button"
                    aria-label={eventLabel(event)}
                    className={`absolute overflow-hidden rounded-md px-1.5 py-0.5 text-left text-xs leading-tight shadow-sm focus-visible:z-30 focus-visible:ring-2 ${
                      draggable(event) ? "touch-none cursor-grab active:cursor-grabbing" : ""
                    } ${isDragging ? "z-30 opacity-80 shadow-lg" : ""}`}
                    style={{
                      ...eventStyle(event, mode),
                      top,
                      height,
                      left: `calc(${(lane / visibleLanes) * 100}% + 2px)`,
                      width: `calc(${100 / visibleLanes}% - 4px)`,
                      transform: shift,
                      transition: isDragging ? "none" : "box-shadow 120ms",
                    }}
                    onPointerDown={handlePointerDown(event)}
                    onPointerMove={handlePointerMove}
                    onPointerUp={handlePointerUp}
                    onPointerCancel={() => setDrag(null)}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!draggable(event)) onSelectDate(event.date);
                    }}
                  >
                    <span className="flex items-center gap-1">
                      <span className="min-w-0 flex-1 truncate font-semibold">{event.campaign_name}</span>
                      <EventIcons event={event} />
                    </span>
                    {duration >= 45 && (
                      <span className="block truncate tabular-nums opacity-80">
                        {isDragging && dragPreview
                          ? windowLabel(
                              event.start_minute + dragPreview.deltaMinutes,
                              event.end_minute + dragPreview.deltaMinutes,
                            )
                          : windowLabel(event.start_minute, event.end_minute, event.overnight)}
                      </span>
                    )}
                  </button>
                );
                return (
                  <div key={`${event.schedule_id}-${event.date}`} className="contents">
                    {renderBlock(event, button)}
                  </div>
                );
              })}
              {clusters.map((cluster) => (
                <Popover
                  key={`overflow-${cluster.index}`}
                  trigger={["click"]}
                  placement="right"
                  title={`${windowLabel(cluster.start, cluster.end)} · ${cluster.events.length} windows`}
                  content={
                    <div className="flex max-h-72 w-64 flex-col gap-1 overflow-y-auto">
                      {cluster.events.map((event) => (
                        <div key={`${event.schedule_id}-${event.date}-overflow`}>{renderChip(event)}</div>
                      ))}
                    </div>
                  }
                >
                  <button
                    type="button"
                    className="absolute right-0.5 z-10 rounded-full border px-1.5 text-[11px] font-semibold shadow-sm focus-visible:ring-2"
                    style={{
                      top: (cluster.start / DAY_MINUTES) * GRID_HEIGHT + 2,
                      background: token.colorBgElevated,
                      borderColor: token.colorBorder,
                    }}
                    aria-label={`${cluster.hidden} more windows between ${windowLabel(cluster.start, cluster.end)}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    +{cluster.hidden}
                  </button>
                </Popover>
              ))}
              {isToday && (
                <div
                  aria-hidden
                  className="pointer-events-none absolute right-0 left-0 z-20"
                  style={{ top: (nowMinute / DAY_MINUTES) * GRID_HEIGHT }}
                  data-testid="now-line"
                >
                  <div className="h-0.5" style={{ background: token.colorError }} />
                  <span
                    className="absolute -top-1 -left-1 h-2.5 w-2.5 rounded-full"
                    style={{ background: token.colorError }}
                  />
                  <span
                    className="absolute -top-2.5 right-1 rounded-sm px-1 text-[10px] font-semibold text-white"
                    style={{ background: token.colorError }}
                  >
                    {minuteLabel(nowMinute)}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {canManage && onSlotClick && (
        <Typography.Text type="secondary" className="sticky bottom-0 left-0 block px-2 py-1 text-xs" style={{ background: token.colorBgContainer }}>
          Click an empty slot to schedule a campaign there; drag a window to move it (you confirm
          before anything is saved).
        </Typography.Text>
      )}
    </div>
  );
}
