import {
  CheckCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  Row,
  Select,
  Space,
  Statistic,
  Switch,
  Tag,
  Typography,
} from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PageHeader } from "@/design-system";
import { ToneTag } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { TVScreen } from "../preview/TVScreen";
import { usePlayback, type PlaybackSlot } from "../preview/playback";
import type { PreviewManifest, PreviewSource } from "../preview/types";
import { manifestToSource } from "../preview/usePreviewSource";
import { PlayerApiError, playerClient, type PlayerCommand, type PlayerEvent } from "./playerClient";

/**
 * Player Simulator — a real player, in the browser.
 *
 * It implements docs/PLAYER_API_CONTRACT.md the way a native LG / Samsung
 * client will: it registers with the tenant's enrollment key, waits for
 * approval, keeps its device token, fetches the manifest with that token
 * (never a user session), renders it through the same renderer the TV
 * preview uses, heartbeats, re-syncs when told to, acknowledges
 * deployments and commands, and reports proof of play for every item it
 * shows. Everything it does lands in the same tables a physical screen
 * writes to, so Devices, Publishing, Monitoring and Reports all react.
 */

const SCREENS = [
  { value: "1920x1080", label: "1920 × 1080 landscape" },
  { value: "1080x1920", label: "1080 × 1920 portrait" },
  { value: "3840x2160", label: "3840 × 2160 (4K)" },
];
const PLAYER_VERSION = "simulator-1.0";
const REGISTER_POLL_MS = 10_000;
const EVENT_FLUSH_MS = 30_000;
const EVENT_FLUSH_COUNT = 50;
const COMMAND_POLL_MS = 5 * 60_000;

type Phase = "idle" | "registering" | "pending" | "running" | "stopped";

interface LogEntry {
  at: string;
  kind: "info" | "ok" | "warn" | "error";
  text: string;
}

interface Stats {
  heartbeats: number;
  syncs: number;
  deploymentsAcked: number;
  commandsAcked: number;
  playbackReported: number;
  lastHeartbeatAt: string | null;
  manifestVersion: number | null;
}

const EMPTY_STATS: Stats = {
  heartbeats: 0,
  syncs: 0,
  deploymentsAcked: 0,
  commandsAcked: 0,
  playbackReported: 0,
  lastHeartbeatAt: null,
  manifestVersion: null,
};

function tokenKey(serial: string) {
  return `sim.device.${serial}`;
}

function readStored(serial: string): { device_id: string; token: string } | null {
  try {
    const raw = localStorage.getItem(tokenKey(serial));
    return raw ? (JSON.parse(raw) as { device_id: string; token: string }) : null;
  } catch {
    return null;
  }
}

function errorText(err: unknown): string {
  if (err instanceof PlayerApiError) return `${err.status} ${err.code}: ${err.message}`;
  if (err instanceof ApiError) return err.message;
  return err instanceof Error ? err.message : String(err);
}

export function SimulatorPage() {
  const { hasPermission } = useAuth();
  const { message } = App.useApp();
  const canManage = hasPermission("devices.manage");
  const [form] = Form.useForm<{ enrollment_key: string; serial_no: string; name: string; screen: string }>();

  const [phase, setPhase] = useState<Phase>("idle");
  const [fast, setFast] = useState(true);
  const [device, setDevice] = useState<{ id: string; token: string | null; serial: string } | null>(null);
  const [manifest, setManifest] = useState<PreviewManifest | null>(null);
  const [stats, setStats] = useState<Stats>(EMPTY_STATS);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [lastError, setLastError] = useState<string | null>(null);

  // Mutable runtime state the timers read without re-rendering.
  const runtime = useRef({
    running: false,
    deviceId: "",
    token: "",
    heartbeatTimer: 0,
    commandTimer: 0,
    flushTimer: 0,
    registerTimer: 0,
    pendingEvents: [] as PlayerEvent[],
    ackedDeployments: new Set<string>(),
    manifestVersion: null as number | null,
    screen: { width: 1920, height: 1080 },
    campaignId: null as string | null,
    playlistId: null as string | null,
  });

  const append = useCallback((kind: LogEntry["kind"], text: string) => {
    setLog((prev) => [{ at: new Date().toISOString(), kind, text }, ...prev].slice(0, 200));
  }, []);

  // Prefill the enrollment key when the user may read it.
  useEffect(() => {
    if (!canManage) return;
    api
      .get<{ enrollment_key: string }>("/devices/enrollment-key")
      .then((r) => r.data && form.setFieldValue("enrollment_key", r.data.enrollment_key))
      .catch(() => undefined);
  }, [canManage, form]);

  useEffect(() => {
    form.setFieldsValue({
      serial_no: `SIM-${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
      name: "Simulated screen",
      screen: "1920x1080",
    });
  }, [form]);

  // ---- contract steps -------------------------------------------------------

  const flushEvents = useCallback(async () => {
    const rt = runtime.current;
    if (!rt.token || rt.pendingEvents.length === 0) return;
    const batch = rt.pendingEvents.splice(0, 500);
    try {
      const out = await playerClient.events(rt.deviceId, rt.token, batch);
      setStats((s) => ({ ...s, playbackReported: s.playbackReported + out.stored_playback }));
      append("ok", `Reported ${out.stored_playback} plays and ${out.stored_events} events`);
    } catch (err) {
      // Offline replay: keep them for the next flush.
      rt.pendingEvents.unshift(...batch);
      append("warn", `Event report failed, ${rt.pendingEvents.length} queued: ${errorText(err)}`);
    }
  }, [append]);

  const syncManifest = useCallback(
    async (reason: string) => {
      const rt = runtime.current;
      if (!rt.token) return;
      try {
        const m = await playerClient.manifest(rt.deviceId, rt.token);
        const changed = m.manifest_version !== rt.manifestVersion;
        rt.manifestVersion = m.manifest_version;
        rt.campaignId = m.active_campaign;
        rt.playlistId = m.playlist?.id ?? null;
        setManifest(m);
        setStats((s) => ({ ...s, syncs: s.syncs + 1, manifestVersion: m.manifest_version }));
        append(
          changed ? "ok" : "info",
          `${reason}: manifest v${m.manifest_version}${changed ? " (new)" : " (unchanged)"} — ${m.campaign?.name ?? "no active campaign"}, ${m.assets.length} assets`,
        );
        // Acknowledge every pending deployment once the content is on screen.
        for (const deploymentId of m.pending_deployments ?? []) {
          if (rt.ackedDeployments.has(deploymentId)) continue;
          try {
            await playerClient.ackDeployment(rt.deviceId, rt.token, deploymentId, true);
            rt.ackedDeployments.add(deploymentId);
            setStats((s) => ({ ...s, deploymentsAcked: s.deploymentsAcked + 1 }));
            append("ok", `Acknowledged deployment ${deploymentId.slice(0, 8)}`);
          } catch (err) {
            append("error", `Deployment ack failed: ${errorText(err)}`);
          }
        }
      } catch (err) {
        append("error", `Manifest fetch failed: ${errorText(err)}`);
        if (err instanceof PlayerApiError && err.status === 401) {
          setLastError("Device token rejected — the device is no longer active. Reset and register again.");
        }
      }
    },
    [append],
  );

  const pollCommands = useCallback(async () => {
    const rt = runtime.current;
    if (!rt.token) return;
    try {
      const commands = await playerClient.commands(rt.deviceId, rt.token);
      for (const cmd of commands as PlayerCommand[]) {
        const type = cmd.command_type;
        let success = true;
        const result: Record<string, unknown> = { simulated: true };
        if (type === "refresh_content") {
          await syncManifest("Command refresh_content");
        } else if (type === "reboot" || type === "restart_player") {
          rt.pendingEvents.push({ type: "APP_STARTED", timestamp: new Date().toISOString(), payload: { version: PLAYER_VERSION, reason: type } });
          await syncManifest(`Command ${type}`);
        } else if (type === "clear_cache") {
          rt.ackedDeployments.clear();
        } else if (type === "screenshot") {
          success = false;
          result.error = "Screenshot capture is not available in the browser simulator";
        } else if (["set_volume", "display_on", "display_off"].includes(type)) {
          result.applied = cmd.payload ?? {};
        } else {
          success = false;
          result.error = `Unknown command type '${type}'`;
        }
        await playerClient.ackCommand(rt.deviceId, rt.token, cmd.id, success, result);
        setStats((s) => ({ ...s, commandsAcked: s.commandsAcked + 1 }));
        append(success ? "ok" : "warn", `Command ${type} acknowledged${success ? "" : " (unsupported)"}`);
      }
    } catch (err) {
      append("error", `Command poll failed: ${errorText(err)}`);
    }
  }, [append, syncManifest]);

  const heartbeat = useCallback(async () => {
    const rt = runtime.current;
    if (!rt.running || !rt.token) return;
    try {
      const out = await playerClient.heartbeat(rt.deviceId, rt.token, {
        timestamp: new Date().toISOString(),
        player_version: PLAYER_VERSION,
        status: "online",
        storage: { used_percent: 12 },
        network: { type: "browser" },
        current: { campaign_id: rt.campaignId, manifest_version: rt.manifestVersion },
      });
      setStats((s) => ({ ...s, heartbeats: s.heartbeats + 1, lastHeartbeatAt: new Date().toISOString() }));
      append("info", `Heartbeat acknowledged (next in ${fast ? 10 : out.heartbeat_interval_seconds}s${out.sync_required ? ", sync required" : ""}${out.pending_commands ? `, ${out.pending_commands} command(s)` : ""})`);
      if (out.sync_required) await syncManifest("Heartbeat");
      if (out.pending_commands > 0) await pollCommands();
      if (out.update) append("warn", `Update offered: release ${out.update.release_id.slice(0, 8)} — the simulator does not install packages`);
      const interval = (fast ? 10 : out.heartbeat_interval_seconds) * 1000;
      window.clearTimeout(rt.heartbeatTimer);
      rt.heartbeatTimer = window.setTimeout(() => void heartbeat(), interval);
    } catch (err) {
      append("error", `Heartbeat failed: ${errorText(err)}`);
      window.clearTimeout(rt.heartbeatTimer);
      if (err instanceof PlayerApiError && err.status === 401) {
        // The contract's one hard stop: the device is no longer active
        // (rejected, decommissioned or its token rotated). Content stays on
        // screen; the player must register again.
        rt.running = false;
        window.clearInterval(rt.commandTimer);
        window.clearInterval(rt.flushTimer);
        setPhase("stopped");
        setLastError("Device token rejected — the device is no longer active. Forget the token and register again.");
        return;
      }
      rt.heartbeatTimer = window.setTimeout(() => void heartbeat(), 30_000);
    }
  }, [append, fast, pollCommands, syncManifest]);

  const startRunning = useCallback(
    async (deviceId: string, token: string, serial: string) => {
      const rt = runtime.current;
      rt.running = true;
      rt.deviceId = deviceId;
      rt.token = token;
      setDevice({ id: deviceId, token, serial });
      setPhase("running");
      setLastError(null);
      try {
        localStorage.setItem(tokenKey(serial), JSON.stringify({ device_id: deviceId, token }));
      } catch {
        // storage unavailable — the token lives for this session only
      }
      append("ok", `Active with a device token — bootstrapping`);
      try {
        await playerClient.capabilities(deviceId, token, [
          { code: "video", supported: true, value: { codecs: ["h264", "vp9"] } },
          { code: "html", supported: true },
          { code: "screenshot", supported: false },
        ]);
        append("info", "Capabilities reported");
      } catch (err) {
        append("warn", `Capabilities not accepted: ${errorText(err)}`);
      }
      rt.pendingEvents.push({ type: "APP_STARTED", timestamp: new Date().toISOString(), payload: { version: PLAYER_VERSION } });
      await syncManifest("Bootstrap");
      await heartbeat();
      await pollCommands();
      window.clearInterval(rt.commandTimer);
      rt.commandTimer = window.setInterval(() => void pollCommands(), COMMAND_POLL_MS);
      window.clearInterval(rt.flushTimer);
      rt.flushTimer = window.setInterval(() => void flushEvents(), EVENT_FLUSH_MS);
    },
    [append, flushEvents, heartbeat, pollCommands, syncManifest],
  );

  const register = useCallback(
    async (values: { enrollment_key: string; serial_no: string; name: string; screen: string }) => {
      const [w, h] = values.screen.split("x").map(Number);
      runtime.current.screen = { width: w, height: h };
      const stored = readStored(values.serial_no);
      if (stored) {
        append("info", `Using the stored token for ${values.serial_no}`);
        await startRunning(stored.device_id, stored.token, values.serial_no);
        return;
      }
      setPhase("registering");
      try {
        const out = await playerClient.register({
          enrollment_key: values.enrollment_key.trim(),
          serial_no: values.serial_no.trim(),
          name: values.name,
          manufacturer: "Simulator",
          model: "Browser",
          platform: "web",
          player_version: PLAYER_VERSION,
          screen_width: w,
          screen_height: h,
        });
        setDevice({ id: out.device_id, token: out.device_token, serial: values.serial_no });
        if (out.status === "active" && out.device_token) {
          await startRunning(out.device_id, out.device_token, values.serial_no);
          return;
        }
        setPhase("pending");
        append("info", `Registered as ${out.status} — waiting for an administrator to approve it in Devices`);
        const poll = async () => {
          try {
            const again = await playerClient.register({ enrollment_key: values.enrollment_key.trim(), serial_no: values.serial_no.trim() });
            if (again.status === "active" && again.device_token) {
              await startRunning(again.device_id, again.device_token, values.serial_no);
              return;
            }
            if (again.status === "rejected" || again.status === "decommissioned") {
              setPhase("stopped");
              setLastError(`The device was ${again.status}.`);
              return;
            }
            append("info", `Still ${again.status}…`);
          } catch (err) {
            append("warn", `Registration poll failed: ${errorText(err)}`);
          }
          runtime.current.registerTimer = window.setTimeout(() => void poll(), REGISTER_POLL_MS);
        };
        runtime.current.registerTimer = window.setTimeout(() => void poll(), REGISTER_POLL_MS);
      } catch (err) {
        setPhase("idle");
        setLastError(errorText(err));
        append("error", `Registration failed: ${errorText(err)}`);
      }
    },
    [append, startRunning],
  );

  const stop = useCallback(async () => {
    const rt = runtime.current;
    rt.running = false;
    window.clearTimeout(rt.heartbeatTimer);
    window.clearTimeout(rt.registerTimer);
    window.clearInterval(rt.commandTimer);
    window.clearInterval(rt.flushTimer);
    await flushEvents();
    setPhase("stopped");
    append("info", "Player stopped — content stays on the last manifest, as a real screen would");
  }, [append, flushEvents]);

  const forget = useCallback(() => {
    const serial = device?.serial ?? form.getFieldValue("serial_no");
    if (serial) {
      try {
        localStorage.removeItem(tokenKey(serial));
      } catch {
        // ignore
      }
    }
    runtime.current.token = "";
    runtime.current.ackedDeployments.clear();
    runtime.current.manifestVersion = null;
    setDevice(null);
    setManifest(null);
    setStats(EMPTY_STATS);
    setPhase("idle");
    setLastError(null);
    append("info", "Forgot the stored token — the next start registers again");
  }, [append, device?.serial, form]);

  const approveNow = useCallback(async () => {
    if (!device) return;
    try {
      await api.post(`/devices/${device.id}/approve`, {});
      message.success("Approved — the player will pick up its token on the next poll");
      append("ok", "Approved from this page (administrator action)");
    } catch (err) {
      message.error(errorText(err));
    }
  }, [append, device, message]);

  // Unmount only: silence the timers without touching state (StrictMode
  // runs this cleanup once on mount as well, so it must be side-effect
  // free beyond the timers).
  useEffect(
    () => () => {
      const rt = runtime.current;
      rt.running = false;
      window.clearTimeout(rt.heartbeatTimer);
      window.clearTimeout(rt.registerTimer);
      window.clearInterval(rt.commandTimer);
      window.clearInterval(rt.flushTimer);
    },
    [],
  );

  // ---- rendering + proof of play -------------------------------------------

  const source: PreviewSource | null = useMemo(
    () =>
      manifest
        ? manifestToSource(manifest, {
            screen_width: runtime.current.screen.width,
            screen_height: runtime.current.screen.height,
            orientation: runtime.current.screen.height > runtime.current.screen.width ? "portrait" : "landscape",
          })
        : null,
    [manifest],
  );
  const items = useMemo(() => source?.playlist?.items ?? [], [source]);
  const slots: PlaybackSlot[] = useMemo(
    () => items.map((item) => ({ key: `${source?.playlist?.id ?? "pl"}-${item.position}`, durationMs: item.duration_ms })),
    [items, source?.playlist?.id],
  );
  const playback = usePlayback(slots, source?.playlist?.loop ?? true, phase === "running");

  // Every slot change closes the previous item's proof-of-play record.
  const current = useRef<{ index: number; startedAt: number } | null>(null);
  useEffect(() => {
    if (phase !== "running" || items.length === 0) {
      current.current = null;
      return;
    }
    const now = Date.now();
    const prev = current.current;
    if (prev && prev.index !== playback.index) {
      const item = items[prev.index];
      if (item) {
        runtime.current.pendingEvents.push({
          type: "playback",
          campaign_id: runtime.current.campaignId,
          playlist_id: runtime.current.playlistId,
          asset_id: item.asset_id ?? null,
          started_at: new Date(prev.startedAt).toISOString(),
          ended_at: new Date(now).toISOString(),
          result: "completed",
        });
        if (runtime.current.pendingEvents.length >= EVENT_FLUSH_COUNT) void flushEvents();
      }
    }
    if (!prev || prev.index !== playback.index) current.current = { index: playback.index, startedAt: now };
  }, [flushEvents, items, phase, playback.index, playback.loopCount]);

  const phaseTag = {
    idle: <ToneTag tone="default">Idle</ToneTag>,
    registering: <ToneTag tone="processing">Registering</ToneTag>,
    pending: <ToneTag tone="warning">Pending approval</ToneTag>,
    running: <ToneTag tone="success">Online</ToneTag>,
    stopped: <ToneTag tone="default">Stopped</ToneTag>,
  }[phase];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Player Simulator"
        description="A real player in the browser: it registers with the enrollment key, holds a device token, renders the manifest, heartbeats, syncs, acknowledges deployments and commands and reports proof of play — exactly as the native LG and Samsung clients will."
      />
      {lastError && <Alert type="error" showIcon message={lastError} closable onClose={() => setLastError(null)} />}

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={15}>
          <Card
            size="small"
            title={
              <Space>
                <span>Screen</span>
                {phaseTag}
                {device && <Typography.Text type="secondary">{device.serial}</Typography.Text>}
              </Space>
            }
            extra={
              phase === "running" ? (
                <Button icon={<StopOutlined />} onClick={() => void stop()}>
                  Stop player
                </Button>
              ) : null
            }
          >
            <div className="rounded-lg bg-black" style={{ height: 460 }}>
              {source ? (
                <TVScreen source={source} playback={playback} muted bezel />
              ) : (
                <div className="flex h-full items-center justify-center text-slate-600 dark:text-slate-400">
                  {phase === "pending" ? "Waiting for approval — nothing to show yet" : "No manifest yet"}
                </div>
              )}
            </div>
            {manifest && (
              <Descriptions size="small" column={{ xs: 1, md: 3 }} className="mt-4">
                <Descriptions.Item label="Campaign">{manifest.campaign?.name ?? "—"}</Descriptions.Item>
                <Descriptions.Item label="Manifest">v{manifest.manifest_version}</Descriptions.Item>
                <Descriptions.Item label="Playlist">
                  {manifest.playlist ? `${manifest.playlist.items.length} items` : "—"}
                </Descriptions.Item>
                <Descriptions.Item label="Now playing">
                  {items[playback.index]?.name ?? items[playback.index]?.item_type ?? "—"}
                </Descriptions.Item>
                <Descriptions.Item label="Loop">{playback.loopCount}</Descriptions.Item>
                <Descriptions.Item label="Timezone">{manifest.timezone}</Descriptions.Item>
              </Descriptions>
            )}
          </Card>
        </Col>

        <Col xs={24} xl={9}>
          <Space orientation="vertical" size="middle" className="w-full">
            <Card size="small" title="Device">
              <Form form={form} layout="vertical" onFinish={(v) => void register(v)} disabled={phase === "running" || phase === "registering" || phase === "pending"}>
                <Form.Item name="enrollment_key" label="Enrollment key" rules={[{ required: true }]} extra={canManage ? "Prefilled from Devices › Show enrollment key." : "Ask an administrator for the tenant's enrollment key."}>
                  <Input.Password autoComplete="off" />
                </Form.Item>
                <Form.Item name="serial_no" label="Serial number" rules={[{ required: true }]}>
                  <Input />
                </Form.Item>
                <Form.Item name="name" label="Device name">
                  <Input />
                </Form.Item>
                <Form.Item name="screen" label="Panel">
                  <Select options={SCREENS} />
                </Form.Item>
                <Space wrap>
                  <Button type="primary" htmlType="submit" icon={<PlayCircleOutlined />} loading={phase === "registering"}>
                    Start player
                  </Button>
                  <Button icon={<ReloadOutlined />} onClick={forget} disabled={false}>
                    Forget token
                  </Button>
                </Space>
              </Form>
              {phase === "pending" && (
                <Alert
                  className="mt-3"
                  type="warning"
                  showIcon
                  message="Pending approval"
                  description={
                    <Space orientation="vertical">
                      <span>The device is registered and waiting. Approve it under Devices, or here if you may.</span>
                      {canManage && (
                        <Button size="small" icon={<CheckCircleOutlined />} onClick={() => void approveNow()}>
                          Approve now
                        </Button>
                      )}
                    </Space>
                  }
                />
              )}
              <div className="mt-3 flex items-center gap-2">
                <Switch checked={fast} onChange={setFast} size="small" aria-label="Fast heartbeat for demos" />
                <Typography.Text type="secondary" className="text-xs">
                  <ThunderboltOutlined /> Fast mode: heartbeat every 10 s instead of the server's interval
                </Typography.Text>
              </div>
            </Card>

            <Card size="small" title="Contract activity">
              <Row gutter={[12, 12]}>
                <Col span={8}><Statistic title="Heartbeats" value={stats.heartbeats} /></Col>
                <Col span={8}><Statistic title="Syncs" value={stats.syncs} /></Col>
                <Col span={8}><Statistic title="Plays reported" value={stats.playbackReported} /></Col>
                <Col span={8}><Statistic title="Deployments acked" value={stats.deploymentsAcked} /></Col>
                <Col span={8}><Statistic title="Commands acked" value={stats.commandsAcked} /></Col>
                <Col span={8}><Statistic title="Queued events" value={runtime.current.pendingEvents.length} /></Col>
              </Row>
              <ul className="m-0 mt-4 max-h-80 list-none overflow-auto p-0 font-mono text-xs" aria-label="Player log">
                {log.length === 0 && <li className="text-slate-600 dark:text-slate-300">Nothing yet — start the player.</li>}
                {log.map((entry, i) => (
                  <li key={`${entry.at}-${i}`} className="flex gap-2 py-0.5">
                    <span className="shrink-0 text-slate-600 dark:text-slate-300">{entry.at.slice(11, 19)}</span>
                    <Tag color={entry.kind === "ok" ? "green" : entry.kind === "warn" ? "gold" : entry.kind === "error" ? "red" : undefined} className="!me-0 shrink-0">
                      {entry.kind}
                    </Tag>
                    <span className="min-w-0 break-words">{entry.text}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </Space>
        </Col>
      </Row>
    </div>
  );
}
