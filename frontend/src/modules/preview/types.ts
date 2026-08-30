import type { LayoutCanvas } from "../design/types";

/** Mirrors `app/services/manifest.py::build_manifest`. This is the player
 * contract — the preview renders exactly what a device would receive, so
 * none of the resolution logic behind it is repeated here. */

export interface ManifestAsset {
  id: string;
  name: string;
  type: string;
  sha256: string | null;
  size: number;
  mime_type: string | null;
  url: string;
}

/** One entry of a published playlist snapshot (`items_json.items`). Only
 * enabled items are snapshotted, so there is no `enabled` flag to honour. */
export interface ManifestItem {
  position: number;
  item_type: "asset" | "layout";
  /** Null means "natural length" — only video and audio may use it, and it
   * has to be resolved from the media element itself. */
  duration_ms: number | null;
  transition: { type?: string } | null;
  asset_id?: string;
  asset_type?: string;
  layout_id?: string;
  name?: string;
}

export interface ManifestPlaylist {
  id: string;
  version: number;
  loop: boolean;
  items: ManifestItem[];
}

export interface ManifestSchedule {
  kind: string;
  start_date: string | null;
  end_date: string | null;
  start_time: string | null;
  end_time: string | null;
  days_of_week: number[] | null;
  timezone: string | null;
  priority: number;
}

export interface PreviewManifest {
  device_id: string;
  manifest_version: number;
  generated_at: string;
  timezone: string;
  active_campaign: string | null;
  campaign_active_now: boolean;
  campaign: { id: string; name: string; priority: number } | null;
  variant: { id: string; name: string } | null;
  experiment?: { id: string; arm: string };
  decision?: { reasons: unknown[] };
  schedules: ManifestSchedule[];
  layout: { id: string; version: number; canvas: LayoutCanvas } | null;
  playlist: ManifestPlaylist | null;
  fallback: ManifestPlaylist | null;
  assets: ManifestAsset[];
  data?: Record<string, unknown>;
  pending_deployments: string[];
}

/** What the renderer stack needs, regardless of where it came from.
 *
 * Device previews build this from a manifest — authoritative, schedule- and
 * targeting-resolved. Composition previews build it from unsaved editor
 * state, which the backend has never seen; `authoritative` is what the UI
 * uses to keep that distinction visible instead of implying a device would
 * play this. */
export interface PreviewSource {
  authoritative: boolean;
  canvas: LayoutCanvas | null;
  playlist: ManifestPlaylist | null;
  /** Signed, playable URLs by asset id. */
  urlByAssetId: Map<string, ManifestAsset>;
  data: Record<string, unknown>;
  timezone: string;
  /** Pixel geometry of the screen being simulated. */
  screen: { width: number; height: number };
  label: string;
  manifest: PreviewManifest | null;
}
