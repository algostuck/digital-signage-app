import { useEffect, useMemo, useRef, useState } from "react";
import { PlaylistItemContent, ZoneContent, type ItemContext } from "./renderers";
import type { Playback } from "./playback";
import type { ManifestItem, PreviewSource } from "./types";
import "./preview.css";

/** Measures the available box so the screen can be fitted on both axes.
 * The Screen Designer scales on width alone, which overflows tall canvases;
 * a TV has to fit entirely or the preview misrepresents the framing. */
function useBoxSize<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width, height });
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return [ref, size] as const;
}

export interface TVScreenProps {
  source: PreviewSource;
  playback: Playback;
  muted: boolean;
  /** Drawn without the bezel when the preview is already full-bleed. */
  bezel?: boolean;
}

export function TVScreen({ source, playback, muted, bezel = true }: TVScreenProps) {
  const [boxRef, box] = useBoxSize<HTMLDivElement>();
  const { width, height } = source.screen;

  // How big the screen itself is drawn.
  const screenScale = useMemo(() => {
    if (!box.width || !box.height || !width || !height) return 0;
    return Math.min(box.width / width, box.height / height);
  }, [box.width, box.height, width, height]);

  // Zone coordinates live in *canvas* space, which is not always the screen's
  // — a 1920×1080 layout on a portrait panel, for instance. The canvas is
  // fitted inside the screen and centred, the way a player letterboxes
  // content whose aspect ratio does not match the display. Scaling zones by
  // the screen instead would push them off the edge.
  const canvasSize = source.canvas
    ? { width: source.canvas.canvas.width, height: source.canvas.canvas.height }
    : { width, height };
  const canvasFit = useMemo(() => {
    if (!canvasSize.width || !canvasSize.height) return 0;
    return Math.min(width / canvasSize.width, height / canvasSize.height);
  }, [width, height, canvasSize.width, canvasSize.height]);
  const zoneScale = canvasFit * screenScale;

  const items = source.playlist?.items ?? [];
  const currentItem: ManifestItem | null = items[playback.index] ?? null;
  const itemKey = currentItem
    ? `${source.playlist?.id ?? "pl"}-${currentItem.position}`
    : "empty";

  const context: ItemContext = {
    source,
    playing: playback.status === "playing",
    muted,
    onNaturalDuration: playback.reportNaturalDuration,
    itemKey,
  };

  const canvas = source.canvas;
  const background = canvas?.canvas.background ?? "#000000";

  // Which zone the campaign's playlist plays in. An explicit `playlist` zone
  // wins; otherwise it is the largest unconfigured `placeholder` zone, which
  // is exactly what `canvas.default_canvas` produces for a new layout and
  // what the Screen Designer leaves a zone as until content is assigned.
  // Without this fallback a layout of plain placeholders renders a frozen
  // screen while its 7-item playlist is ignored.
  const playlistZoneKey = useMemo(() => {
    const zones = canvas?.zones ?? [];
    const explicit = zones.find((z) => z.content_type === "playlist");
    if (explicit) return explicit.key;
    const slots = zones
      .filter((z) => z.content_type === "placeholder")
      .sort((a, b) => b.width * b.height - a.width * a.height);
    return slots[0]?.key ?? null;
  }, [canvas]);

  return (
    <div
      ref={boxRef}
      className={`flex h-full w-full items-center justify-center overflow-hidden ${
        playback.status === "playing" ? "" : "dsc-preview-paused"
      }`}
    >
      <div
        // The screen itself. `role="img"` with a label keeps it from reading
        // as an unlabelled region to a screen reader; the live description
        // of what is playing lives in the controls below.
        role="img"
        aria-label={`Simulated screen, ${width} by ${height} pixels`}
        style={{
          width: width * screenScale,
          height: height * screenScale,
          background,
          position: "relative",
          overflow: "hidden",
          flex: "none",
          borderRadius: bezel ? 6 : 0,
          boxShadow: bezel
            ? "0 0 0 10px #0a0a0a, 0 0 0 11px #2b2b2b, 0 24px 48px rgba(0,0,0,0.55)"
            : undefined,
        }}
      >
        {screenScale > 0 && canvas ? (
          <div
            style={{
              position: "absolute",
              width: canvasSize.width * zoneScale,
              height: canvasSize.height * zoneScale,
              left: (width * screenScale - canvasSize.width * zoneScale) / 2,
              top: (height * screenScale - canvasSize.height * zoneScale) / 2,
            }}
          >
            {[...canvas.zones]
              .sort((a, b) => a.z_index - b.z_index)
              .map((zone) => (
                <div
                  key={zone.key}
                  style={{
                    position: "absolute",
                    left: zone.x * zoneScale,
                    top: zone.y * zoneScale,
                    width: zone.width * zoneScale,
                    height: zone.height * zoneScale,
                    zIndex: zone.z_index,
                    overflow: "hidden",
                    background: (zone.style.background as string | null) ?? "transparent",
                    transform: zone.rotation ? `rotate(${zone.rotation}deg)` : undefined,
                    // Lets zone content size itself against the zone rather
                    // than the viewport, so text scales with the screen.
                    containerType: "size",
                  }}
                >
                  <ZoneContent
                    zone={zone}
                    context={context}
                    currentItem={zone.key === playlistZoneKey ? currentItem : null}
                  />
                </div>
              ))}
          </div>
        ) : screenScale > 0 && currentItem ? (
          // No layout resolved: the playlist owns the whole screen, which is
          // what a device does when its campaign has a playlist but no layout.
          <div className="h-full w-full" key={itemKey}>
            <PlaylistItemContent item={currentItem} context={context} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
