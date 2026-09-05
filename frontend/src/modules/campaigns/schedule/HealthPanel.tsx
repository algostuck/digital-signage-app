import {
  CheckCircleOutlined,
  DesktopOutlined,
  FlagOutlined,
  LockOutlined,
  PlayCircleOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Button, Card, Col, Progress, Row, Skeleton, Space, Typography } from "antd";
import { StatCard } from "@/design-system";
import { STATUS_TEXT } from "@/design-system";
import { ToneTag } from "@/design-system";
import { useThemeMode } from "@/design-system";
import type { CalendarData } from "../types";

/** The five real numbers of the visible range. Nothing here is invented:
 * every figure is a count the API computed for exactly this range and
 * filter set. */
export function SummaryStrip({ calendar, loading }: { calendar: CalendarData | null; loading: boolean }) {
  const summary = calendar?.summary;
  const conflicts = summary?.conflicts_actionable ?? 0;
  const items = [
    { label: "Campaigns scheduled", value: summary?.campaigns ?? 0, icon: <FlagOutlined /> },
    { label: "Screens covered", value: summary?.screens ?? 0, icon: <DesktopOutlined /> },
    { label: "Play windows", value: summary?.play_windows ?? 0, icon: <PlayCircleOutlined /> },
    { label: "Blackout windows", value: summary?.blackout_windows ?? 0, icon: <LockOutlined /> },
    {
      label: "Actionable conflicts",
      value: conflicts,
      icon: conflicts ? <WarningOutlined /> : <CheckCircleOutlined />,
      tone: (conflicts ? "error" : "success") as "error" | "success",
    },
  ];
  return (
    <Row gutter={[12, 12]} className="mb-4" data-testid="summary-strip">
      {items.map((item) => (
        <Col key={item.label} flex="1 1 150px">
          <StatCard label={item.label} value={item.value} icon={item.icon} tone={item.tone} loading={loading} />
        </Col>
      ))}
    </Row>
  );
}

/**
 * Schedule Health replaces the old "N conflicts" alert: how much of the
 * range is clean, how many items actually need a decision, at what
 * severity, and one button that opens the list to act on.
 */
export function HealthPanel({
  calendar,
  loading,
  onReview,
  onShowOnlyConflicts,
  showingOnlyConflicts,
}: {
  calendar: CalendarData | null;
  loading: boolean;
  onReview: () => void;
  onShowOnlyConflicts: (on: boolean) => void;
  showingOnlyConflicts: boolean;
}) {
  const { mode } = useThemeMode();
  const summary = calendar?.summary;
  if (loading && !summary) {
    return (
      <Card size="small" className="mb-4">
        <Skeleton active paragraph={{ rows: 1 }} />
      </Card>
    );
  }
  const playWindows = summary?.play_windows ?? 0;
  const flagged = (calendar?.events ?? []).filter((e) => e.conflict).length;
  const clean = playWindows === 0 ? 100 : Math.round(((playWindows - flagged) / playWindows) * 100);
  const actionable = summary?.conflicts_actionable ?? 0;
  const high = summary?.conflicts_high ?? 0;
  const medium = summary?.conflicts_medium ?? 0;
  const low = summary?.conflicts_low ?? 0;
  const estate = summary?.conflicts_total_estate ?? 0;
  const status = high > 0 ? "error" : actionable > 0 ? "warning" : "success";

  return (
    <Card size="small" className="mb-4" data-testid="health-panel" styles={{ body: { padding: "12px 16px" } }}>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="flex items-center gap-3">
          <Progress
            type="circle"
            size={56}
            percent={clean}
            strokeColor={STATUS_TEXT[mode][status]}
            format={(p) => <span style={{ color: STATUS_TEXT[mode][status], fontSize: 13, fontWeight: 600 }}>{p}%</span>}
            aria-label={`${clean}% of play windows are free of actionable conflicts`}
          />
          <div>
            <Typography.Text strong className="block">
              Schedule health
            </Typography.Text>
            <Typography.Text type="secondary" className="block text-xs">
              {playWindows === 0
                ? "No play windows in this range."
                : `${playWindows - flagged} of ${playWindows} play windows are conflict-free`}
            </Typography.Text>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {actionable === 0 ? (
            <ToneTag tone="success" icon={<CheckCircleOutlined />}>
              No actionable conflicts
            </ToneTag>
          ) : (
            <>
              <Typography.Text strong style={{ color: STATUS_TEXT[mode][status] }}>
                {actionable} need{actionable === 1 ? "s" : ""} a decision
              </Typography.Text>
              {high > 0 && <ToneTag tone="error">{high} high</ToneTag>}
              {medium > 0 && <ToneTag tone="warning">{medium} medium</ToneTag>}
            </>
          )}
          {low > 0 && (
            <ToneTag tone="default" title="Involving draft, pending or expired campaigns — informational">
              {low} informational
            </ToneTag>
          )}
          {estate > actionable && (
            <Typography.Text type="secondary" className="text-xs">
              {estate - actionable} more outside the current filters
            </Typography.Text>
          )}
        </div>
        <Space className="ml-auto" wrap>
          <Button
            size="small"
            type={showingOnlyConflicts ? "primary" : "default"}
            onClick={() => onShowOnlyConflicts(!showingOnlyConflicts)}
            aria-pressed={showingOnlyConflicts}
          >
            {showingOnlyConflicts ? "Showing conflicts only" : "Show conflicts only"}
          </Button>
          <Button size="small" type="primary" icon={<WarningOutlined />} onClick={onReview} disabled={(calendar?.conflicts.length ?? 0) === 0}>
            Review conflicts
          </Button>
        </Space>
      </div>
    </Card>
  );
}
