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

  const scale = useMemo(() => {
    if (!box.width || !box.height || !width || !height) return 0;
    return Math.min(box.width / width, box.height / height);
  }, [box.width, box.height, width, height]);

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
          width: width * scale,
          height: height * scale,
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
        {scale > 0 && canvas ? (
          [...canvas.zones]
            .sort((a, b) => a.z_index - b.z_index)
            .map((zone) => (
              <div
                key={zone.key}
                style={{
                  position: "absolute",
                  left: zone.x * scale,
                  top: zone.y * scale,
                  width: zone.width * scale,
                  height: zone.height * scale,
                  zIndex: zone.z_index,
                  overflow: "hidden",
                  background: (zone.style.background as string | null) ?? "transparent",
                  transform: zone.rotation ? `rotate(${zone.rotation}deg)` : undefined,
                  // Lets zone content size itself against the zone rather
                  // than the viewport, so text scales with the screen.
                  containerType: "size",
                }}
              >
                <ZoneContent zone={zone} context={context} currentItem={currentItem} />
              </div>
            ))
        ) : scale > 0 && currentItem ? (
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
