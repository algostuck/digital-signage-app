import { Col, Row } from "antd";
import type { ReactNode } from "react";
import { ErrorState } from "../../components/ui/states";
import { useAuth } from "../../lib/auth";
import { PRESET_LABELS, useDashboardRange, useDashboardRefresh, useOrganizationDashboard } from "./api";
import { useDashboardLayout, WIDGETS, type WidgetKey } from "./customise";
import { WidgetBoundary } from "./WidgetBoundary";
import { ActivityWidget } from "./widgets/ActivityWidget";
import { ApprovalsWidget } from "./widgets/ApprovalsWidget";
import { AttentionWidget } from "./widgets/AttentionWidget";
import { CampaignWidget } from "./widgets/CampaignWidget";
import { ContentWidget } from "./widgets/ContentWidget";
import { DashboardHeader } from "./widgets/DashboardHeader";
import { DeploymentWidget } from "./widgets/DeploymentWidget";
import { DeviceHealthWidget } from "./widgets/DeviceHealthWidget";
import { InsightsWidget } from "./widgets/InsightsWidget";
import { KpiGrid } from "./widgets/KpiGrid";
import { LiveScreensWidget } from "./widgets/LiveScreensWidget";
import { LocationMapWidget } from "./widgets/LocationMapWidget";
import { NowPlayingWidget } from "./widgets/NowPlayingWidget";
import { PlaybackWidget } from "./widgets/PlaybackWidget";
import { ScheduleTodayWidget } from "./widgets/ScheduleTodayWidget";
import { TopLocationsWidget } from "./widgets/TopLocationsWidget";
import { UsageWidget } from "./widgets/UsageWidget";

/** Column span per widget on ≥ xl. 15/9 is the codebase's golden split;
 * 12/12 where the halves carry equal weight; 24 for full-width strips. */
const SPAN: Record<WidgetKey, number> = {
  kpis: 24,
  device_health: 15,
  attention: 9,
  map: 15,
  campaigns: 9,
  playback: 15,
  deployments: 9,
  content: 12,
  locations_top: 12,
  now_playing: 15,
  activity: 9,
  live_screens: 24,
  approvals: 12,
  schedule: 12,
  usage: 12,
  insights: 12,
};

/** SCR-02 Organization dashboard — the executive command centre. One
 * aggregate query feeds every widget; each widget owns its own states and
 * renders nothing when the server omitted its section (no permission). */
export function DashboardPage() {
  const { user } = useAuth();
  const { range, setPreset, setCustom } = useDashboardRange();
  const { data, query } = useOrganizationDashboard(range);
  const refresh = useDashboardRefresh();
  const layout = useDashboardLayout(user?.id);
  const rangeLabel = PRESET_LABELS[range.preset] === "Custom" ? `${range.from} → ${range.to}` : PRESET_LABELS[range.preset];

  const loading = query.isPending;
  const error = query.error;
  const retry = () => void query.refetch();

  if (error && !data) {
    return (
      <ErrorState
        title="Unable to load the dashboard"
        description="The dashboard service did not respond. Your data is safe — try again."
        onRetry={retry}
      />
    );
  }

  const common = { loading, error: undefined, onRetry: retry };
  const widgets: Record<WidgetKey, ReactNode> = {
    kpis: <KpiGrid kpis={data?.kpis} loading={loading} rangeLabel={rangeLabel} />,
    device_health: data?.device_health || loading ? <DeviceHealthWidget health={data?.device_health} {...common} /> : null,
    attention: data?.attention || loading ? <AttentionWidget items={data?.attention} {...common} /> : null,
    map: data?.geo || loading ? <LocationMapWidget anchors={data?.geo} {...common} /> : null,
    campaigns: data?.campaigns || loading ? <CampaignWidget campaigns={data?.campaigns} rangeLabel={rangeLabel} {...common} /> : null,
    playback: data?.playback || loading ? <PlaybackWidget playback={data?.playback} totals={data?.kpis?.playback} rangeLabel={rangeLabel} {...common} /> : null,
    deployments: data?.deployments || loading ? <DeploymentWidget deployments={data?.deployments} rangeLabel={rangeLabel} {...common} /> : null,
    content: data?.content || loading ? <ContentWidget content={data?.content} {...common} /> : null,
    locations_top: data?.locations_top || loading ? <TopLocationsWidget locations={data?.locations_top} {...common} /> : null,
    now_playing: data?.now_playing || loading ? <NowPlayingWidget items={data?.now_playing} {...common} /> : null,
    live_screens: data?.now_playing ? <LiveScreensWidget items={data.now_playing} loading={loading} /> : null,
    activity: data?.activity || loading ? <ActivityWidget items={data?.activity} {...common} /> : null,
    approvals: data?.approvals ? <ApprovalsWidget items={data.approvals} {...common} /> : null,
    schedule: data?.schedule_today || loading ? <ScheduleTodayWidget events={data?.schedule_today} {...common} /> : null,
    usage: data?.usage || loading ? <UsageWidget usage={data?.usage} {...common} /> : null,
    insights: data?.insights ? <InsightsWidget items={data.insights} {...common} /> : null,
  };

  return (
    <div>
      <DashboardHeader
        range={range}
        setPreset={setPreset}
        setCustom={setCustom}
        generatedAt={data?.generated_at ?? null}
        onRefresh={() => void refresh()}
        refreshing={query.isFetching}
        layout={layout}
      />
      <Row gutter={[16, 16]}>
        {layout.order
          .filter((key) => layout.isVisible(key) && widgets[key])
          .map((key) => (
            <Col key={key} xs={24} xl={SPAN[key]}>
              <WidgetBoundary title={WIDGETS.find((w) => w.key === key)?.label ?? key}>
                {widgets[key]}
              </WidgetBoundary>
            </Col>
          ))}
      </Row>
    </div>
  );
}
