import { Tag, Timeline, Typography } from "antd";
import { minuteLabel } from "../api";
import { ChartFrame } from "../charts/ChartFrame";
import type { ScheduleEvent } from "../types";
import { ViewAll } from "./shared";

export function ScheduleTodayWidget({
  events,
  loading,
  error,
  onRetry,
}: {
  events?: ScheduleEvent[];
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  return (
    <ChartFrame
      title="Today's schedule"
      extra={<ViewAll to="/schedules" label="Calendar" />}
      loading={loading && !events}
      error={error}
      onRetry={onRetry}
      empty={!!events && events.length === 0}
      emptyTitle="No campaigns scheduled today"
      emptyDescription="Published campaigns with a window today appear here in order."
    >
      <Timeline
        className="mt-2"
        items={events?.map((e) => ({
          color: e.live ? "green" : e.conflict ? "red" : "blue",
          children: (
            <div className="flex flex-wrap items-center gap-2">
              <Typography.Text type="secondary" className="tabular-nums text-xs">
                {minuteLabel(e.start_minute)}–{minuteLabel(e.end_minute)}
              </Typography.Text>
              <Typography.Text strong>{e.campaign_name}</Typography.Text>
              {e.live && (
                <Tag color="success" variant="filled" className="!me-0">
                  Live now
                </Tag>
              )}
              {e.conflict && (
                <Tag color="error" variant="filled" className="!me-0">
                  Conflict
                </Tag>
              )}
              {e.kind === "blackout" && (
                <Tag variant="filled" className="!me-0">
                  Blackout
                </Tag>
              )}
            </div>
          ),
        }))}
      />
    </ChartFrame>
  );
}
