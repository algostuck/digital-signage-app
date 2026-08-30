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
  conflict: boolean;
}

export interface CalendarData {
  range_start: string;
  range_end: string;
  events: CalendarEvent[];
  conflict_count: number;
}

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function minuteLabel(minute: number): string {
  const h = Math.floor(minute / 60);
  const m = minute % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}
