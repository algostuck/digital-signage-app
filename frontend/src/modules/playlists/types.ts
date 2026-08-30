export interface PlaylistItem {
  id: string;
  position: number;
  item_type: "asset" | "layout";
  asset_id: string | null;
  layout_id: string | null;
  duration_ms: number | null;
  transition_json: { type?: string } | null;
  enabled: boolean;
  name: string;
  asset_type: string | null;
  thumbnail_url: string | null;
  ready: boolean;
}

export interface PlaylistSummary {
  id: string;
  name: string;
  description: string | null;
  status: string;
  loop_enabled: boolean;
  fallback_playlist_id: string | null;
  current_version_no: number | null;
  item_count: number;
  total_duration_ms: number;
  created_at: string;
  updated_at: string;
}

export interface PlaylistDetail extends PlaylistSummary {
  items: PlaylistItem[];
  versions: { id: string; version_no: number; published_at: string }[];
}

export function formatDuration(ms: number): string {
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}
