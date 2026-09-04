import { Col, Row, Statistic, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { EntitlementGuard } from "../../../components/ui/EntitlementGuard";
import { ChartFrame } from "../charts/ChartFrame";
import { RankBar } from "../charts/RankBar";
import { useThemeMode } from "../../../theme/ThemeProvider";
import { STATUS_COLORS, STATUS_TEXT } from "../charts/theme";
import { TrendLine } from "../charts/TrendLine";
import type { PlaybackBlock, PlaybackTotals } from "../types";
import { dayLabel, ViewAll } from "./shared";

export function PlaybackWidget({
  playback,
  totals,
  loading,
  error,
  onRetry,
  rangeLabel,
}: {
  playback?: PlaybackBlock;
  totals?: PlaybackTotals;
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
  rangeLabel: string;
}) {
  const { mode } = useThemeMode();
  const navigate = useNavigate();
  const summary =
    totals && playback
      ? `${totals.plays.toLocaleString()} plays ${rangeLabel.toLowerCase()} from ${totals.devices} screens` +
        (totals.completion_rate != null ? `, ${totals.completion_rate}% completed.` : ".")
      : undefined;

  return (
    <EntitlementGuard feature="proof_of_play" featureName="Proof of play">
      <ChartFrame
        title="Playback / proof of play"
        extra={<ViewAll to="/reports" label="Reports" />}
        summary={summary}
        loading={loading && !playback}
        error={error}
        onRetry={onRetry}
        empty={!!totals && totals.plays === 0}
        emptyTitle="No playback in this range"
        emptyDescription="Screens report proof of play as they show content. Try a wider range."
      >
        {playback && totals && (
          <>
            <Row gutter={[16, 8]} className="mb-3">
              <Col xs={12} md={6}>
                <Statistic title="Plays" value={totals.plays} />
              </Col>
              <Col xs={12} md={6}>
                <Statistic title="Completed" value={totals.completed} styles={{ content: { color: STATUS_TEXT[mode].success } }} />
              </Col>
              <Col xs={12} md={6}>
                <Statistic title="Failed" value={totals.failed} styles={{ content: { color: totals.failed ? STATUS_TEXT[mode].error : undefined } }} />
              </Col>
              <Col xs={12} md={6}>
                <Statistic
                  title="Completion"
                  value={totals.completion_rate ?? 0}
                  suffix="%"
                  precision={1}
                />
              </Col>
            </Row>
            <TrendLine
              height={200}
              xLabel={dayLabel}
              series={[
                { key: "plays", label: "Plays", color: STATUS_COLORS.plays, points: playback.series.map((p) => ({ x: p.date, y: p.plays })) },
                { key: "completed", label: "Completed", color: STATUS_COLORS.completed, points: playback.series.map((p) => ({ x: p.date, y: p.completed })) },
                { key: "failed", label: "Failed", color: STATUS_COLORS.failed, points: playback.series.map((p) => ({ x: p.date, y: p.failed })) },
              ]}
            />
            {playback.top_assets.length > 0 && (
              <div className="mt-4">
                <Typography.Text strong className="text-[13px]">
                  Most played
                </Typography.Text>
                <RankBar
                  ariaLabel="Most played content"
                  rows={playback.top_assets.map((a) => ({
                    key: a.asset_id,
                    label: a.name,
                    sublabel: `${a.type} · ${a.devices} screens`,
                    value: a.plays,
                    display: `${a.plays.toLocaleString()} plays`,
                    color: STATUS_COLORS.plays,
                    onClick: () => navigate(`/content?type=${a.type}`),
                  }))}
                />
              </div>
            )}
          </>
        )}
      </ChartFrame>
    </EntitlementGuard>
  );
}
