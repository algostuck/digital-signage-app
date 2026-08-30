import {
  CaretRightOutlined,
  CompressOutlined,
  ExpandOutlined,
  PauseOutlined,
  ReloadOutlined,
  SoundOutlined,
  StepBackwardOutlined,
  StepForwardOutlined,
} from "@ant-design/icons";
import { AudioMutedOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Col,
  Descriptions,
  Empty,
  Flex,
  Modal,
  Progress,
  Row,
  Space,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ErrorState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { formatDuration } from "../playlists/types";
import { TVScreen } from "./TVScreen";
import { formatClock, usePlayback, type PlaybackSlot } from "./playback";
import type { PreviewSource } from "./types";

export interface TVPreviewModalProps {
  open: boolean;
  onClose(): void;
  title: string;
  source: PreviewSource | null;
  loading?: boolean;
  error?: string | null;
  onRetry?(): void;
  /** Rendered above the screen — the schedule-time picker in device mode. */
  toolbar?: React.ReactNode;
}

export function TVPreviewModal({
  open,
  onClose,
  title,
  source,
  loading,
  error,
  onRetry,
  toolbar,
}: TVPreviewModalProps) {
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [muted, setMuted] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);

  const items = useMemo(() => source?.playlist?.items ?? [], [source]);
  const slots: PlaybackSlot[] = useMemo(
    () =>
      items.map((item) => ({
        key: `${source?.playlist?.id ?? "pl"}-${item.position}`,
        durationMs: item.duration_ms,
      })),
    [items, source?.playlist?.id],
  );
  const playback = usePlayback(slots, source?.playlist?.loop ?? true, open);

  useEffect(() => {
    function onChange() {
      setFullscreen(document.fullscreenElement === stageRef.current);
    }
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  // Leaving fullscreen behind a closed modal would strand the browser in a
  // fullscreen element that no longer exists.
  useEffect(() => {
    if (!open && document.fullscreenElement) void document.exitFullscreen().catch(() => {});
  }, [open]);

  const toggleFullscreen = useCallback(() => {
    const node = stageRef.current;
    if (!node) return;
    if (document.fullscreenElement) void document.exitFullscreen().catch(() => {});
    else void node.requestFullscreen().catch(() => {});
  }, []);

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      // Never steal keys from a focused control (the date picker, buttons).
      const tag = (event.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      switch (event.key) {
        case " ":
          event.preventDefault();
          playback.toggle();
          break;
        case "ArrowRight":
          playback.next();
          break;
        case "ArrowLeft":
          playback.previous();
          break;
        case "m":
          setMuted((m) => !m);
          break;
        case "f":
          toggleFullscreen();
          break;
        default:
          break;
      }
    },
    [playback, toggleFullscreen],
  );

  const current = items[playback.index] ?? null;
  const duration = playback.currentDurationMs;
  const percent = duration ? Math.min(100, (playback.elapsedMs / duration) * 100) : 0;
  const manifest = source?.manifest ?? null;

  const controls = (
    <Flex wrap align="center" justify="space-between" gap="small" className="w-full">
      <Space>
        <Tooltip title="Previous (←)">
          <Button
            icon={<StepBackwardOutlined />}
            onClick={playback.previous}
            disabled={items.length < 2}
            aria-label="Previous item"
          />
        </Tooltip>
        <Tooltip title={playback.status === "playing" ? "Pause (space)" : "Play (space)"}>
          <Button
            type="primary"
            icon={playback.status === "playing" ? <PauseOutlined /> : <CaretRightOutlined />}
            onClick={playback.toggle}
            disabled={items.length === 0}
            aria-label={playback.status === "playing" ? "Pause" : "Play"}
          />
        </Tooltip>
        <Tooltip title="Next (→)">
          <Button
            icon={<StepForwardOutlined />}
            onClick={playback.next}
            disabled={items.length < 2}
            aria-label="Next item"
          />
        </Tooltip>
        <Tooltip title="Restart">
          <Button icon={<ReloadOutlined />} onClick={playback.restart} aria-label="Restart" />
        </Tooltip>
      </Space>
      <Space>
        <Tooltip title={muted ? "Unmute (m)" : "Mute (m)"}>
          <Button
            icon={muted ? <AudioMutedOutlined /> : <SoundOutlined />}
            onClick={() => setMuted((m) => !m)}
            aria-label={muted ? "Unmute" : "Mute"}
          />
        </Tooltip>
        <Tooltip title={fullscreen ? "Exit fullscreen (f)" : "Fullscreen (f)"}>
          <Button
            icon={fullscreen ? <CompressOutlined /> : <ExpandOutlined />}
            onClick={toggleFullscreen}
            aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          />
        </Tooltip>
      </Space>
    </Flex>
  );

  const stage = (
    <div
      ref={stageRef}
      className="flex flex-col gap-2 rounded-lg p-2"
      style={{ background: "#0b0b0d" }}
    >
      <div style={{ height: fullscreen ? "calc(100vh - 96px)" : 420 }}>
        {source ? (
          <TVScreen source={source} playback={playback} muted={muted} bezel={!fullscreen} />
        ) : null}
      </div>
      <div className="px-1">
        <Progress
          percent={percent}
          showInfo={false}
          size="small"
          status={playback.status === "playing" ? "active" : "normal"}
          aria-label="Current item progress"
        />
        <Flex justify="space-between" className="mt-1">
          <Typography.Text className="text-xs" style={{ color: "rgba(255,255,255,0.75)" }}>
            {current ? `${playback.index + 1}/${items.length} · ${current.name ?? "Item"}` : "—"}
          </Typography.Text>
          <Typography.Text className="text-xs" style={{ color: "rgba(255,255,255,0.75)" }}>
            {formatClock(playback.elapsedMs)}
            {duration ? ` / ${formatClock(duration)}` : ""}
          </Typography.Text>
        </Flex>
      </div>
      <div className="px-1 pb-1">{controls}</div>
    </div>
  );

  const queue = items.length ? (
    <div className="max-h-[420px] overflow-auto">
      {items.map((item, index) => {
        const active = index === playback.index;
        return (
          <button
            key={`${item.position}-${item.name ?? index}`}
            type="button"
            onClick={() => playback.goTo(index)}
            aria-current={active ? "true" : undefined}
            className={`flex w-full items-center justify-between gap-2 rounded px-2 py-2 text-left ${
              active ? "bg-[rgba(29,78,216,0.12)]" : ""
            }`}
          >
            <Space size={8} align="center">
              <Typography.Text type="secondary" className="tabular-nums text-xs">
                {String(index + 1).padStart(2, "0")}
              </Typography.Text>
              <Typography.Text strong={active} ellipsis className="max-w-[190px]">
                {item.name ?? item.asset_id ?? "Item"}
              </Typography.Text>
            </Space>
            <Typography.Text type="secondary" className="text-xs">
              {item.duration_ms != null ? formatDuration(item.duration_ms) : "natural"}
            </Typography.Text>
          </button>
        );
      })}
    </div>
  ) : (
    <Empty description="No playable items" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  );

  const details = (
    <Descriptions column={1} size="small" bordered>
      <Descriptions.Item label="Campaign">
        {manifest?.campaign?.name ?? source?.label ?? "—"}
      </Descriptions.Item>
      {manifest && (
        <Descriptions.Item label="Active now">
          <Tag color={manifest.campaign_active_now ? "success" : "default"} variant="filled">
            {manifest.campaign_active_now ? "In a schedule window" : "Outside every window"}
          </Tag>
        </Descriptions.Item>
      )}
      {manifest?.variant && (
        <Descriptions.Item label="Variant">{manifest.variant.name}</Descriptions.Item>
      )}
      {manifest?.experiment && (
        <Descriptions.Item label="Experiment arm">{manifest.experiment.arm}</Descriptions.Item>
      )}
      <Descriptions.Item label="Layout">
        {manifest?.layout ? `v${manifest.layout.version}` : source?.canvas ? "Draft" : "—"}
      </Descriptions.Item>
      <Descriptions.Item label="Playlist">
        {source?.playlist ? `v${source.playlist.version} · ${items.length} items` : "—"}
      </Descriptions.Item>
      <Descriptions.Item label="Loop">
        {source?.playlist?.loop ? "Yes" : "No"}
      </Descriptions.Item>
      <Descriptions.Item label="Screen">
        {source ? `${source.screen.width}×${source.screen.height}` : "—"}
      </Descriptions.Item>
      <Descriptions.Item label="Timezone">{source?.timezone ?? "—"}</Descriptions.Item>
      {manifest && (
        <Descriptions.Item label="Manifest">v{manifest.manifest_version}</Descriptions.Item>
      )}
    </Descriptions>
  );

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={1180}
      centered
      destroyOnHidden
      title={
        <Space align="center" wrap>
          <span>{title}</span>
          {source &&
            (source.authoritative ? (
              <StatusBadge status="published" />
            ) : (
              <Tag color="warning" variant="filled">
                Draft composition
              </Tag>
            ))}
        </Space>
      }
    >
      <div onKeyDown={onKeyDown} tabIndex={-1}>
        {toolbar && <div className="mb-3">{toolbar}</div>}
        {source && !source.authoritative && (
          <Alert
            type="info"
            showIcon
            className="mb-3"
            message="This previews the current draft, not what a device would play."
            description="Schedules, targeting and decisioning are not applied here. Use a device preview to see the resolved screen."
          />
        )}
        {error ? (
          <ErrorState title="Preview unavailable" description={error} onRetry={onRetry} />
        ) : loading ? (
          <LoadingState rows={8} />
        ) : !source ? (
          <Empty description="Nothing to preview" />
        ) : (
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={16}>
              {stage}
            </Col>
            <Col xs={24} lg={8}>
              <Tabs
                items={[
                  { key: "queue", label: `Queue (${items.length})`, children: queue },
                  { key: "details", label: "Details", children: details },
                ]}
              />
            </Col>
          </Row>
        )}
      </div>
    </Modal>
  );
}
