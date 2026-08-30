import { useEffect, useRef, useState } from "react";
import type { ZoneDef } from "../design/types";
import type { ManifestAsset, ManifestItem, PreviewSource } from "./types";

/** Renderers for the simulated screen. Everything here draws *inside* the
 * TV, so it deliberately ignores the app's light/dark theme — a display
 * shows what the layout says, on whatever background the canvas defines. */

interface ItemContext {
  source: PreviewSource;
  /** Playback tells media elements whether to run. */
  playing: boolean;
  muted: boolean;
  /** Called with the media's own length when the item had no duration set. */
  onNaturalDuration(key: string, ms: number): void;
  itemKey: string;
}

function ZoneFallback({ label, detail }: { label: string; detail?: string }) {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-1 p-2 text-center">
      <span className="text-[0.7rem] font-medium uppercase tracking-wide text-white/70">
        {label}
      </span>
      {detail && <span className="text-[0.65rem] text-white/45">{detail}</span>}
    </div>
  );
}

function transitionClass(item: ManifestItem | null): string {
  switch (item?.transition?.type) {
    case "fade":
      return "dsc-preview-fade";
    case "slide":
      return "dsc-preview-slide";
    default:
      return "";
  }
}

/** An image or video from the playlist, or bound to an image/video zone. */
function AssetMedia({
  asset,
  item,
  context,
  objectFit = "contain",
}: {
  asset: ManifestAsset | undefined;
  item: ManifestItem | null;
  context: ItemContext;
  objectFit?: "contain" | "cover";
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [failed, setFailed] = useState(false);
  const [blocked, setBlocked] = useState(false);

  const isVideo =
    asset?.type === "video" || (asset?.mime_type ?? "").startsWith("video/");

  useEffect(() => {
    setFailed(false);
    setBlocked(false);
  }, [asset?.id]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (context.playing) {
      // Autoplay can be refused even when muted; surface that rather than
      // showing a frozen frame that reads as a broken preview.
      void video.play().then(
        () => setBlocked(false),
        () => setBlocked(true),
      );
    } else {
      video.pause();
    }
  }, [context.playing, asset?.id]);

  // Detach the source on unmount so closing the preview stops the download
  // and releases the decoder immediately.
  useEffect(() => {
    const video = videoRef.current;
    return () => {
      if (!video) return;
      video.pause();
      video.removeAttribute("src");
      video.load();
    };
  }, []);

  if (!asset) {
    return <ZoneFallback label="Asset unavailable" detail={item?.name ?? undefined} />;
  }
  if (failed) {
    return (
      <ZoneFallback
        label={isVideo ? "Video cannot be played" : "Image cannot be loaded"}
        detail={asset.name}
      />
    );
  }

  if (isVideo) {
    return (
      <div className="relative h-full w-full">
        <video
          ref={videoRef}
          src={asset.url}
          muted={context.muted}
          playsInline
          // A clip shorter than its configured duration repeats to fill the
          // slot; the playback clock, not the video, decides when to advance.
          loop={item?.duration_ms != null}
          className="h-full w-full"
          style={{ objectFit }}
          onLoadedMetadata={(e) => {
            const seconds = e.currentTarget.duration;
            if (Number.isFinite(seconds) && seconds > 0) {
              context.onNaturalDuration(context.itemKey, seconds * 1000);
            }
          }}
          onError={() => setFailed(true)}
        />
        {blocked && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60">
            <ZoneFallback label="Autoplay blocked" detail="Press play to start" />
          </div>
        )}
      </div>
    );
  }

  return (
    <img
      src={asset.url}
      alt={asset.name}
      draggable={false}
      className="h-full w-full"
      style={{ objectFit }}
      onError={() => setFailed(true)}
    />
  );
}

function TickerZone({ text, playing }: { text: string; playing: boolean }) {
  // Duplicated content plus a -50% translation makes the scroll seamless.
  const seconds = Math.max(8, Math.min(60, text.length * 0.35));
  return (
    <div className="flex h-full w-full items-center overflow-hidden">
      <div
        className="dsc-preview-ticker"
        style={{
          animationDuration: `${seconds}s`,
          animationPlayState: playing ? "running" : "paused",
        }}
      >
        <span>{text}</span>
        <span aria-hidden>{text}</span>
      </div>
    </div>
  );
}

function ClockZone({ timezone, running }: { timezone: string; running: boolean }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, [running]);

  let label: string;
  try {
    label = new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZone: timezone,
    }).format(now);
  } catch {
    label = new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(now);
  }
  return (
    <div className="flex h-full w-full items-center justify-center">
      <span
        className="font-semibold tabular-nums text-white"
        style={{ fontSize: "clamp(0.9rem, 22cqw, 6rem)" }}
      >
        {label}
      </span>
    </div>
  );
}

function WidgetZone({ zone, data }: { zone: ZoneDef; data: Record<string, unknown> }) {
  const bound = data[zone.key];
  if (bound === undefined) {
    return (
      <ZoneFallback
        label={zone.name}
        detail={zone.widget ? "Widget — no data snapshot" : "Widget not configured"}
      />
    );
  }
  // The manifest ships the transform already applied, so this only has to
  // display the snapshot — never re-derive it.
  const rows = Array.isArray(bound) ? bound : [bound];
  return (
    <div className="h-full w-full overflow-hidden p-2">
      <ul className="m-0 list-none space-y-1 p-0">
        {rows.slice(0, 8).map((row, i) => (
          <li key={i} className="truncate text-[0.7rem] text-white/85">
            {typeof row === "object" && row !== null
              ? Object.values(row as Record<string, unknown>).slice(0, 3).join(" · ")
              : String(row)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function WebZone({ url }: { url: string }) {
  const [failed, setFailed] = useState(false);
  if (!url || failed) {
    return <ZoneFallback label="Web zone" detail={url || "No URL configured"} />;
  }
  return (
    <iframe
      src={url}
      title={`Web zone ${url}`}
      className="h-full w-full border-0"
      // Preview only: never let embedded pages reach the console session.
      sandbox="allow-scripts allow-same-origin"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}

/** Dispatches a single layout zone. `currentItem` is passed only to the zone
 * hosting the campaign's playlist; every other zone runs on its own timeline
 * and is never reset by the playlist advancing. */
export function ZoneContent({
  zone,
  context,
  currentItem,
}: {
  zone: ZoneDef;
  context: ItemContext;
  currentItem: ManifestItem | null;
}) {
  const { source } = context;
  const text = String(zone.content_config.text ?? zone.name);

  // The host zone plays the playlist whatever it is declared as — it may be
  // an explicit `playlist` zone or an unconfigured `placeholder` slot.
  if (currentItem) {
    return (
      <div className={`h-full w-full ${transitionClass(currentItem)}`} key={context.itemKey}>
        <PlaylistItemContent item={currentItem} context={context} />
      </div>
    );
  }

  switch (zone.content_type) {
    case "playlist":
      return <ZoneFallback label="Playlist" detail="No item to play" />;
    case "image":
    case "video":
      return (
        <AssetMedia
          asset={source.urlByAssetId.get(String(zone.content_config.asset_id ?? ""))}
          item={null}
          context={context}
          objectFit="cover"
        />
      );
    case "text":
      return (
        <div className="flex h-full w-full items-center px-2">
          <span className="text-white/90">{text}</span>
        </div>
      );
    case "ticker":
      return <TickerZone text={text} playing={context.playing} />;
    case "clock":
      return <ClockZone timezone={source.timezone} running={context.playing} />;
    case "web":
      return <WebZone url={String(zone.content_config.url ?? "")} />;
    case "widget":
      return <WidgetZone zone={zone} data={source.data} />;
    case "qr":
      // Rendering a real QR code needs an encoder this app does not ship;
      // showing a fake one would be worse than showing the target.
      return <ZoneFallback label="QR code" detail={String(zone.content_config.url ?? zone.name)} />;
    default:
      return <ZoneFallback label={zone.name} detail={zone.content_type} />;
  }
}

/** One playlist item: an asset, or a nested layout reference. */
export function PlaylistItemContent({
  item,
  context,
}: {
  item: ManifestItem;
  context: ItemContext;
}) {
  if (item.item_type === "layout") {
    // Nested layouts are pinned by version in the snapshot but the manifest
    // does not inline their canvas, so there is nothing to draw here.
    return <ZoneFallback label="Layout item" detail={item.name ?? item.layout_id} />;
  }
  return (
    <AssetMedia
      asset={context.source.urlByAssetId.get(String(item.asset_id ?? ""))}
      item={item}
      context={context}
    />
  );
}

export type { ItemContext };
