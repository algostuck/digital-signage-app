import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { Asset } from "../content/types";
import type { LayoutCanvas } from "../design/types";
import type { Device } from "../devices/types";
import type { PlaylistDetail } from "../playlists/types";
import type { ManifestAsset, ManifestPlaylist, PreviewManifest, PreviewSource } from "./types";

/** Signed URLs live for `signed_url_ttl_seconds` (900s). Refetching at 10
 * minutes keeps a long preview session playing instead of failing zones
 * once the URLs lapse. */
const URL_REFRESH_MS = 10 * 60 * 1000;

const DEFAULT_SCREEN = { width: 1920, height: 1080 };

/** Device geometry wins; the layout's own canvas is the next best answer,
 * because it is what the content was actually composed against. */
function resolveScreen(
  device: Pick<Device, "screen_width" | "screen_height" | "orientation"> | null,
  canvas: LayoutCanvas | null,
): { width: number; height: number } {
  let base = DEFAULT_SCREEN;
  if (device?.screen_width && device?.screen_height) {
    base = { width: device.screen_width, height: device.screen_height };
  } else if (canvas?.canvas.width && canvas.canvas.height) {
    base = { width: canvas.canvas.width, height: canvas.canvas.height };
  }
  // `Device.orientation` is a free-form string, unlike the layout's union,
  // so normalise before trusting it.
  const orientation = (device?.orientation ?? "").toLowerCase();
  const isPortrait = orientation.startsWith("portrait");
  const isLandscape = orientation.startsWith("landscape");
  if (isPortrait && base.width > base.height) {
    return { width: base.height, height: base.width };
  }
  if (isLandscape && base.height > base.width) {
    return { width: base.height, height: base.width };
  }
  return base;
}

function indexAssets(assets: ManifestAsset[]): Map<string, ManifestAsset> {
  return new Map(assets.map((a) => [a.id, a]));
}

/**
 * Device preview: the authoritative answer. The manifest has already
 * resolved schedule, targeting, decisioning, experiments and variants
 * server-side, and ships signed URLs, so nothing is re-derived here.
 */
export function useDevicePreviewSource(
  device: Device | null,
  at: string | null,
  enabled: boolean,
) {
  const query = useQuery({
    queryKey: ["preview-manifest", device?.id, at],
    queryFn: () =>
      api.get<PreviewManifest>(
        `/devices/${device!.id}/preview-manifest${at ? `?at=${encodeURIComponent(at)}` : ""}`,
      ),
    enabled: enabled && device != null,
    refetchInterval: URL_REFRESH_MS,
    staleTime: URL_REFRESH_MS,
  });

  const manifest = query.data?.data ?? null;
  const source: PreviewSource | null = manifest ? manifestToSource(manifest, device) : null;

  return { source, query };
}

/** A device manifest, as the player contract delivers it, turned into what
 * the renderer stack needs. Shared by the operator's TV preview (which
 * fetches it with a user session) and the Player Simulator (which fetches
 * it with a device token), so both render exactly the same thing. */
export function manifestToSource(
  manifest: PreviewManifest,
  device: Pick<Device, "screen_width" | "screen_height" | "orientation"> | null,
): PreviewSource {
  const canvas = (manifest.layout?.canvas as LayoutCanvas | undefined) ?? null;
  return {
    authoritative: true,
    canvas,
    playlist: manifest.playlist,
    urlByAssetId: indexAssets(manifest.assets),
    data: manifest.data ?? {},
    timezone: manifest.timezone,
    screen: resolveScreen(device, canvas),
    label: manifest.campaign?.name ?? "No campaign resolved",
    manifest,
  };
}

/** Every asset id the composition needs a playable URL for. */
function compositionAssetIds(
  canvas: LayoutCanvas | null,
  playlist: ManifestPlaylist | null,
): string[] {
  const ids = new Set<string>();
  for (const item of playlist?.items ?? []) {
    if (item.asset_id) ids.add(item.asset_id);
  }
  for (const zone of canvas?.zones ?? []) {
    const id = zone.content_config.asset_id;
    if (id) ids.add(String(id));
  }
  return [...ids].sort();
}

/**
 * Composition preview: unsaved editor state the backend has never seen.
 * It cannot answer "what will play on a screen" — no schedule or targeting
 * is involved — so callers must present it as a composition, not a device.
 */
export function useCompositionPreviewSource(input: {
  canvas: LayoutCanvas | null;
  playlist: ManifestPlaylist | null;
  label: string;
  timezone?: string;
  enabled: boolean;
}) {
  const { canvas, playlist, label, timezone, enabled } = input;
  const ids = compositionAssetIds(canvas, playlist);

  const query = useQuery({
    queryKey: ["preview-asset-urls", ids],
    enabled: enabled && ids.length > 0,
    refetchInterval: URL_REFRESH_MS,
    staleTime: URL_REFRESH_MS,
    queryFn: async () => {
      // Resolved by id, never from a paged list: the Screen Designer's
      // page-1 asset window silently drops anything past the first 100.
      const resolved = await Promise.all(
        ids.map(async (id) => {
          try {
            const [asset, signed] = await Promise.all([
              api.get<Asset>(`/assets/${id}`),
              api.get<{ url: string; expires_in: number }>(`/assets/${id}/download-url`),
            ]);
            if (!signed.data?.url) return null;
            return {
              id,
              name: asset.data?.name ?? id,
              type: asset.data?.type ?? "",
              sha256: asset.data?.checksum ?? null,
              size: asset.data?.current_version?.size_bytes ?? 0,
              mime_type: asset.data?.current_version?.mime_type ?? null,
              url: signed.data.url,
            } satisfies ManifestAsset;
          } catch {
            // One unreadable asset must not blank the whole preview; its
            // zone renders an error state instead.
            return null;
          }
        }),
      );
      return resolved.filter((a): a is ManifestAsset => a !== null);
    },
  });

  const source: PreviewSource | null = enabled
    ? {
        authoritative: false,
        canvas,
        playlist,
        urlByAssetId: indexAssets(query.data ?? []),
        data: {},
        timezone: timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone,
        screen: resolveScreen(null, canvas),
        label,
        manifest: null,
      }
    : null;

  return { source, query };
}

/** Adapts a playlist the editor is holding into the manifest's item shape,
 * so both preview modes feed the same renderers. */
export function playlistToManifestShape(playlist: PlaylistDetail): ManifestPlaylist {
  return {
    id: playlist.id,
    version: playlist.current_version_no ?? 0,
    loop: playlist.loop_enabled,
    items: playlist.items
      .filter((item) => item.enabled)
      .sort((a, b) => a.position - b.position)
      .map((item, index) => ({
        position: index + 1,
        item_type: item.item_type,
        duration_ms: item.duration_ms,
        transition: item.transition_json,
        asset_id: item.asset_id ?? undefined,
        asset_type: item.asset_type ?? undefined,
        layout_id: item.layout_id ?? undefined,
        name: item.name,
      })),
  };
}
