import { useQuery } from "@tanstack/react-query";
import { Card, Col, Row, Skeleton, Typography } from "antd";
import { useMemo, useState } from "react";
import { ChartFrame } from "@/design-system";
import { api } from "../../../lib/api";
import type { Device } from "../../devices/types";
import { DeviceTVPreview } from "../../preview";
import { usePlayback, type PlaybackSlot } from "../../preview/playback";
import { TVScreen } from "../../preview/TVScreen";
import { useDevicePreviewSource } from "../../preview/usePreviewSource";
import type { NowPlayingItem } from "../types";

/** One screen, rendered by the TV preview engine from its real manifest —
 * what the device resolves to right now, not a stored screenshot. The tile
 * is an antd Card acting as a button (keyboard-activatable). */
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
  const open = () => d && onOpen(d);

  return (
    <Card
      size="small"
      hoverable
      role="button"
      tabIndex={0}
      aria-label={`Open TV preview for ${name}`}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          open();
        }
      }}
      styles={{ body: { padding: 8 } }}
    >
      <div style={{ borderRadius: 8, padding: 8, background: "#0b0b0d", height: 150 }}>
        {source ? (
          <TVScreen source={source} playback={playback} muted bezel={false} />
        ) : (
          <Skeleton.Node active style={{ width: "100%", height: 126 }} />
        )}
      </div>
      <Typography.Text ellipsis style={{ display: "block", marginTop: 4, textAlign: "center", fontSize: 12 }}>
        {name}
      </Typography.Text>
    </Card>
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
      <Row gutter={[12, 12]}>
        {picks.map((p) => (
          <Col key={p.device_id} xs={24} sm={8}>
            <MiniScreen deviceId={p.device_id} name={p.device_name} onOpen={setOpen} />
          </Col>
        ))}
      </Row>
      <DeviceTVPreview device={open} open={open != null} onClose={() => setOpen(null)} />
    </ChartFrame>
  );
}
