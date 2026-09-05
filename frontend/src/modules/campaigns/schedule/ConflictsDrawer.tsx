import { CalendarOutlined, DesktopOutlined, ExportOutlined } from "@ant-design/icons";
import { Button, Drawer, Empty, List, Segmented, Space, Typography } from "antd";
import { useState } from "react";
import { ToneTag } from "../../../components/ui/ToneTag";
import type { ConflictSeverity, ScheduleConflict } from "../types";
import { formatDayShort, windowLabel } from "./dates";
import { REASON_LABEL, SEVERITY_LABEL, severityTone, statusLabel, statusTone } from "./palette";

/**
 * The actionable list behind "Review conflicts": one card per grouped
 * conflict with the campaigns, the window, the dates, the screens it
 * affects, the reason and what to do about it. Actions open the campaign
 * or jump the calendar to the first affected day.
 */
export function ConflictsDrawer({
  open,
  onClose,
  conflicts,
  focusId,
  onOpenCampaign,
  onShowOnCalendar,
}: {
  open: boolean;
  onClose: () => void;
  conflicts: ScheduleConflict[];
  focusId?: string | null;
  onOpenCampaign: (campaignId: string) => void;
  onShowOnCalendar: (conflict: ScheduleConflict) => void;
}) {
  const [severity, setSeverity] = useState<ConflictSeverity | "all">("all");
  const visible = conflicts.filter((c) => severity === "all" || c.severity === severity);
  const counts = {
    high: conflicts.filter((c) => c.severity === "high").length,
    medium: conflicts.filter((c) => c.severity === "medium").length,
    low: conflicts.filter((c) => c.severity === "low").length,
  };

  return (
    <Drawer
      title="Scheduling conflicts"
      open={open}
      onClose={onClose}
      size={560}
      placement="right"
      destroyOnHidden
      extra={
        <Segmented
          size="small"
          value={severity}
          onChange={(v) => setSeverity(v as ConflictSeverity | "all")}
          options={[
            { value: "all", label: `All (${conflicts.length})` },
            { value: "high", label: `High (${counts.high})` },
            { value: "medium", label: `Medium (${counts.medium})` },
            { value: "low", label: `Info (${counts.low})` },
          ]}
        />
      }
    >
      <Typography.Paragraph type="secondary" className="text-xs">
        A conflict is listed only when two windows overlap <em>on the same screens</em>. High = equal
        priority on live campaigns (the player picks by tie-break). Medium = a window that never
        plays because a higher priority covers it, or sits inside its own blackout. Info = involves a
        draft, pending, paused or expired campaign.
      </Typography.Paragraph>
      {visible.length === 0 ? (
        <Empty description="No conflicts at this severity" />
      ) : (
        <List
          dataSource={visible}
          rowKey="id"
          renderItem={(conflict) => {
            const [first, second] = conflict.campaigns;
            const focused = conflict.id === focusId;
            return (
              <List.Item
                className={focused ? "rounded-md ring-2 ring-offset-1" : undefined}
                data-testid={`conflict-${conflict.id}`}
              >
                <div className="w-full">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <ToneTag tone={severityTone(conflict.severity)} className="!mr-0">
                      {SEVERITY_LABEL[conflict.severity]}
                    </ToneTag>
                    <Typography.Text strong>{REASON_LABEL[conflict.reason]}</Typography.Text>
                  </div>
                  <Typography.Paragraph className="!mb-2 text-xs" type="secondary">
                    {conflict.message}
                  </Typography.Paragraph>
                  <ul className="m-0 mb-2 list-none space-y-1 p-0 text-sm">
                    {[first, second].map((c) => (
                      <li key={c.schedule_id} className="flex flex-wrap items-center gap-1.5">
                        <Button
                          type="link"
                          size="small"
                          className="!h-auto !p-0 font-medium"
                          onClick={() => onOpenCampaign(c.campaign_id)}
                        >
                          {c.campaign_name}
                        </Button>
                        <ToneTag tone={statusTone(c.campaign_status)} className="!mr-0">
                          {statusLabel(c.campaign_status)}
                        </ToneTag>
                        <Typography.Text type="secondary" className="text-xs">
                          {c.kind === "blackout" ? "blackout" : `priority ${c.campaign_priority}`}
                          {c.schedule_name ? ` · ${c.schedule_name}` : ""}
                          {conflict.winner_campaign_id === c.campaign_id && conflict.reason !== "inside_blackout"
                            ? " · plays"
                            : ""}
                        </Typography.Text>
                      </li>
                    ))}
                  </ul>
                  <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                    <span>
                      <CalendarOutlined aria-hidden /> {windowLabel(conflict.window[0], conflict.window[1])} ·{" "}
                      {conflict.dates.count === 1
                        ? formatDayShort(conflict.dates.first)
                        : `${formatDayShort(conflict.dates.first)} – ${formatDayShort(conflict.dates.last)} (${
                            conflict.dates.count
                          } days)`}
                    </span>
                    <span>
                      <DesktopOutlined aria-hidden /> {conflict.screens_affected.count} screen
                      {conflict.screens_affected.count === 1 ? "" : "s"}
                      {conflict.screens_affected.names.length > 0 && (
                        <Typography.Text type="secondary">
                          {" "}
                          — {conflict.screens_affected.names.join(", ")}
                          {conflict.screens_affected.count > conflict.screens_affected.names.length ? ", …" : ""}
                        </Typography.Text>
                      )}
                    </span>
                  </div>
                  {conflict.suggestions.length > 0 && (
                    <div className="mb-2 text-xs">
                      <Typography.Text type="secondary">How to resolve: </Typography.Text>
                      {conflict.suggestions.join(" · ")}
                    </div>
                  )}
                  <Space size="small" wrap>
                    <Button size="small" icon={<CalendarOutlined />} onClick={() => onShowOnCalendar(conflict)}>
                      Show on calendar
                    </Button>
                    <Button size="small" icon={<ExportOutlined />} onClick={() => onOpenCampaign(first.campaign_id)}>
                      Open {first.campaign_name.length > 24 ? "campaign" : first.campaign_name}
                    </Button>
                  </Space>
                </div>
              </List.Item>
            );
          }}
        />
      )}
    </Drawer>
  );
}
