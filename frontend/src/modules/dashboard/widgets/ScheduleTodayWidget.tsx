import { Timeline, Typography } from "antd";
import { minuteLabel } from "../api";
import { ToneTag } from "../../../components/ui/ToneTag";
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
          content: (
            <div className="flex flex-wrap items-center gap-2">
              <Typography.Text type="secondary" className="tabular-nums text-xs">
                {minuteLabel(e.start_minute)}–{minuteLabel(e.end_minute)}
              </Typography.Text>
              <Typography.Text strong>{e.campaign_name}</Typography.Text>
              {e.live && (
                <ToneTag tone="success" className="!me-0">
                  Live now
                </ToneTag>
              )}
              {e.conflict && (
                <ToneTag tone="error" className="!me-0">
                  Conflict
                </ToneTag>
              )}
              {e.kind === "blackout" && (
                <ToneTag tone="default" className="!me-0">
                  Blackout
                </ToneTag>
              )}
            </div>
          ),
        }))}
      />
    </ChartFrame>
  );
}
