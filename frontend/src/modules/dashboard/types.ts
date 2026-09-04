/** Contract for `GET /dashboard/organization` (`app/services/dashboard.py`).
 *
 * Every section is optional on the wire: the server omits what the caller
 * is not permitted to see. Widgets treat `undefined` as "not permitted" and
 * render nothing; an empty array or zero is real data. */

export interface DeviceCounts {
  total: number;
  active: number;
  online: number;
  warning: number;
  offline: number;
  pending: number;
}

export interface PlaybackTotals {
  plays: number;
  completed: number;
  failed: number;
  completion_rate: number | null;
  devices: number;
}

export interface Kpis {
  devices: DeviceCounts;
  content: { total: number; published: number; draft: number };
  campaigns: {
    published: number;
    pending_approval: number;
    approved: number;
    draft: number;
    paused: number;
  };
  deployments: { publishing: number; partial: number; published: number; failed: number };
  playback: PlaybackTotals;
  locations: { total: number };
}

export interface HealthPoint {
  at: string;
  online: number;
  warning: number;
  offline: number;
  na: number;
}

export interface DeviceHealth {
  current: { online: number; warning: number; offline: number; na: number };
  thresholds: {
    warning_after_seconds: number;
    offline_after_seconds: number;
    min_player_version?: string | null;
  };
  trend: HealthPoint[];
  trend_granularity: "hour" | "day";
}

export interface GeoAnchor {
  location_id: string;
  name: string;
  type: string | null;
  latitude: number;
  longitude: number;
  city: string | null;
  state: string | null;
  devices: number;
  online: number;
  warning: number;
  offline: number;
  campaigns: number;
  health_pct: number | null;
}

export interface TopLocation {
  location_id: string;
  name: string;
  city: string | null;
  devices: number;
  online: number;
  health_pct: number | null;
}

export interface TopCampaign {
  id: string;
  name: string;
  status: string;
  priority: number;
  plays: number;
  updated_at: string | null;
  devices: number;
  acknowledged: number;
  failed: number;
  pending: number;
}

export interface CampaignsBlock {
  by_status: Record<string, number>;
  top: TopCampaign[];
}

export interface PlaybackPoint {
  date: string;
  plays: number;
  completed: number;
  failed: number;
}

export interface TopAsset {
  asset_id: string;
  name: string;
  type: string;
  plays: number;
  devices: number;
}

export interface PlaybackBlock {
  series: PlaybackPoint[];
  top_assets: TopAsset[];
}

export interface RecentAsset {
  id: string;
  name: string;
  type: string;
  status: string;
  created_at: string | null;
  thumbnail_url: string | null;
}

export interface ContentBlock {
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  recent: RecentAsset[];
}

export interface DeploymentHistoryPoint {
  date: string;
  acknowledged: number;
  failed: number;
  pending: number;
}

export interface RecentDeployment {
  id: string;
  campaign_id: string;
  campaign_name: string;
  version: number;
  status: string;
  started_at: string | null;
  created_at: string | null;
  total_devices: number;
  acknowledged: number;
  failed: number;
  pending: number;
}

export interface DeploymentsBlock {
  by_status: Record<string, number>;
  history: DeploymentHistoryPoint[];
  failed_devices_in_range: number;
  recent: RecentDeployment[];
}

export type Severity = "critical" | "high" | "medium" | "info";

export interface AttentionItem {
  key: string;
  severity: Severity;
  count: number;
  label: string;
  detail: string | null;
  href: string;
  action: string;
}

export interface ActivityItem {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  entity_name: string | null;
  user_name: string | null;
  created_at: string | null;
}

export interface ApprovalItem {
  id: string;
  entity_type: string;
  entity_id: string;
  entity_name: string | null;
  requester_name: string | null;
  submitted_at: string | null;
}

export interface ScheduleEvent {
  campaign_id: string;
  campaign_name: string;
  kind: string;
  start_minute: number;
  end_minute: number;
  live: boolean;
  conflict: boolean;
}

export interface NowPlayingItem {
  device_id: string;
  device_name: string;
  location_name: string | null;
  connection_status: string | null;
  campaign_name: string | null;
  asset_name: string | null;
  asset_type: string | null;
  thumbnail_url: string | null;
  reported_at: string | null;
  source: "reported" | "scheduled";
}

export interface UsageMetric {
  used: number;
  limit: number | null;
}

export interface UsageBlock {
  plan_code: string | null;
  plan_name: string | null;
  subscription_status: string | null;
  period_end: string | null;
  billing_cycle: string | null;
  devices: UsageMetric;
  users: UsageMetric;
  storage_mb: UsageMetric;
  locations: UsageMetric;
}

export interface Insight {
  id: string;
  device_id: string;
  device_name: string;
  signal: string | null;
  score: number;
  finding: string;
  why: string | null;
  action: string | null;
  opened_at: string | null;
  href: string;
}

export interface OrganizationDashboard {
  generated_at: string;
  timezone: string;
  range: { from: string; to: string };
  kpis?: Kpis;
  device_health?: DeviceHealth;
  geo?: GeoAnchor[];
  locations_top?: TopLocation[];
  campaigns?: CampaignsBlock;
  playback?: PlaybackBlock;
  content?: ContentBlock;
  deployments?: DeploymentsBlock;
  attention?: AttentionItem[];
  activity?: ActivityItem[];
  approvals?: ApprovalItem[];
  schedule_today?: ScheduleEvent[];
  now_playing?: NowPlayingItem[];
  usage?: UsageBlock;
  insights?: Insight[];
}

/** The global time filter. Point-in-time widgets ignore it. */
export type RangePreset = "today" | "yesterday" | "7d" | "30d" | "90d" | "custom";

export interface DashboardRange {
  preset: RangePreset;
  from: string; // YYYY-MM-DD
  to: string; // YYYY-MM-DD
}
