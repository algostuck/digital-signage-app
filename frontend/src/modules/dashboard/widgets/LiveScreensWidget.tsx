import { useQuery } from "@tanstack/react-query";
import { Skeleton, Typography } from "antd";
import { useMemo, useState } from "react";
import { api } from "../../../lib/api";
import type { Device } from "../../devices/types";
import { DeviceTVPreview } from "../../preview";
import { usePlayback, type PlaybackSlot } from "../../preview/playback";
import { TVScreen } from "../../preview/TVScreen";
import { useDevicePreviewSource } from "../../preview/usePreviewSource";
import { ChartFrame } from "@/design-system";
import type { NowPlayingItem } from "../types";

/** One screen, rendered by the TV preview engine from its real manifest —
 * what the device resolves to right now, not a stored screenshot. */
function MiniScreen({ deviceId, name, onOpen }: { deviceId: string; name: string; onOpen: (d: Device) => void }) {
  const device = useQuery({
    queryKey: ["device", deviceId],
    queryFn: () => api.get<Device>(`/devices/${deviceId}`),
    staleTime: 60_000,
  });
  const d = device.data?.data ?? null;
  const { source } = useDevicePreviewSource(d, null, d != null);
  const slots: PlaybackSlot[] = useMemo(
    () =>
      (source?.playlist?.items ?? []).map((item) => ({
        key: `${source?.playlist?.id ?? "pl"}-${item.position}`,
        durationMs: item.duration_ms,
      })),
    [source],
  );
  const playback = usePlayback(slots, source?.playlist?.loop ?? true, true);

  return (
    <button
      type="button"
      onClick={() => d && onOpen(d)}
      className="block w-full rounded-lg text-left"
      aria-label={`Open TV preview for ${name}`}
    >
      <div className="rounded-lg p-2" style={{ background: "#0b0b0d", height: 150 }}>
        {source ? (
          <TVScreen source={source} playback={playback} muted bezel={false} />
        ) : (
          <Skeleton.Node active style={{ width: "100%", height: 126 }} />
        )}
      </div>
      <Typography.Text ellipsis className="mt-1 block text-center text-xs">
        {name}
      </Typography.Text>
    </button>
  );
}

export function LiveScreensWidget({ items, loading }: { items?: NowPlayingItem[]; loading: boolean }) {
  const [open, setOpen] = useState<Device | null>(null);
  const picks = (items ?? []).slice(0, 3);
  if (!loading && picks.length === 0) return null;

  return (
    <ChartFrame
      title="Live screens"
      summary="Rendered from each device's current manifest by the TV preview engine — the same content the screen is playing."
      loading={loading && !items}
    >
      <div className="grid gap-3 sm:grid-cols-3">
        {picks.map((p) => (
          <MiniScreen key={p.device_id} deviceId={p.device_id} name={p.device_name} onOpen={setOpen} />
        ))}
      </div>
      <DeviceTVPreview device={open} open={open != null} onClose={() => setOpen(null)} />
    </ChartFrame>
  );
}
