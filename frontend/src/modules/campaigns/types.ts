export interface Schedule {
  id: string;
  campaign_id: string;
  name: string | null;
  kind: "play" | "blackout";
  start_date: string | null;
  end_date: string | null;
  start_time: string | null;
  end_time: string | null;
  days_of_week: number[] | null;
  recurrence_json: { days_of_month?: number[] } | null;
  exception_dates_json: string[] | null;
  timezone: string | null;
  priority: number;
  expired: boolean;
}

export interface VariantTarget {
  target_type: "location" | "device" | "group" | "tag";
  target_id: string;
  include_descendants: boolean;
}

export interface CampaignVariant {
  id: string;
  name: string;
  layout_id: string | null;
  playlist_id: string | null;
  priority: number;
  targets: VariantTarget[];
}

export interface ConflictOverlap {
  date: string;
  window: [number, number];
  campaigns: {
    campaign_id: string;
    campaign_name: string;
    campaign_priority: number;
    schedule_priority: number;
  }[];
  winner_campaign_id: string;
  winner_campaign_name: string;
  conflict: boolean;
  reason: string;
}

export interface CampaignSummary {
  id: string;
  name: string;
  description: string | null;
  status: string;
  priority: number;
  playlist_id: string | null;
  layout_id: string | null;
  schedule_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignTarget {
  id: string;
  target_type: "location" | "device" | "group" | "tag";
  target_id: string;
  include_descendants: boolean;
  is_exclusion: boolean;
}

export interface CampaignDetail extends CampaignSummary {
  schedules: Schedule[];
  targets: CampaignTarget[];
  variants: CampaignVariant[];
}

export interface DeploymentSummary {
  id: string;
  campaign_id: string;
  campaign_name: string;
  version: number;
  status: string;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  total_devices: number;
  acknowledged: number;
  failed: number;
  pending: number;
}

export interface DeploymentDeviceRow {
  device_id: string;
  device_name: string;
  status: string;
  attempts: number;
  last_error: string | null;
  acknowledged_at: string | null;
}

export type RecurrenceType = "once" | "daily" | "weekly" | "monthly";
export type ConflictSeverity = "high" | "medium" | "low";
export type ConflictReason =
  | "equal_priority_shared_screens"
  | "shadowed_by_priority"
  | "inside_blackout";

/** One schedule on one day, as the schedule workspace contract returns it
 * (docs/SCHEDULE_UX_AUDIT.md §10.2). Minutes are wall-clock in the
 * event's own timezone (`timezone`, else the tenant zone). */
export interface CalendarEvent {
  schedule_id: string;
  campaign_id: string;
  campaign_name: string;
  schedule_name: string | null;
  date: string;
  start_minute: number;
  end_minute: number;
  priority: number;
  campaign_priority: number;
  timezone: string | null;
  kind: "play" | "blackout";
  overnight: boolean;
  /** True only for actionable (high / medium) conflicts on a play window. */
  conflict: boolean;
  campaign_status: string | null;
  recurrence_type: RecurrenceType;
  recurrence_text: string;
  days_of_week: number[] | null;
  expired: boolean;
  /** The window covers the server's "now" and the campaign is published. */
  live: boolean;
  screens: number;
  locations: number;
  conflict_ids: string[];
}

export interface ConflictCampaign {
  campaign_id: string;
  campaign_name: string;
  campaign_status: string | null;
  campaign_priority: number;
  schedule_id: string;
  schedule_name: string | null;
  schedule_priority: number;
  kind: "play" | "blackout";
}

/** One actionable conflict grouped across the range (§10.3). */
export interface ScheduleConflict {
  id: string;
  severity: ConflictSeverity;
  reason: ConflictReason;
  message: string;
  window: [number, number];
  campaigns: ConflictCampaign[];
  winner_campaign_id: string | null;
  screens_affected: { count: number; names: string[] };
  dates: { first: string; last: string; count: number };
  suggestions: string[];
}

export interface CalendarSummary {
  campaigns: number;
  screens: number;
  play_windows: number;
  blackout_windows: number;
  conflicts_actionable: number;
  conflicts_high: number;
  conflicts_medium: number;
  conflicts_low: number;
  conflicts_total_estate: number;
}

export interface CalendarNow {
  at: string;
  date: string;
  minute: number;
}

export interface CalendarData {
  range_start: string;
  range_end: string;
  timezone: string;
  now: CalendarNow | null;
  events: CalendarEvent[];
  conflicts: ScheduleConflict[];
  summary: CalendarSummary | null;
  /** Actionable conflicts in the (filtered) range. */
  conflict_count: number;
}

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function minuteLabel(minute: number): string {
  const h = Math.floor(minute / 60);
  const m = minute % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** Civil date of a local Date as YYYY-MM-DD. Never via toISOString(),
 * which is UTC and shifts the day for anyone east of Greenwich. */
export function isoDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
