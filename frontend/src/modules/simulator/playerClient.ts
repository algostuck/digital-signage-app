/**
 * The device side of the Player API contract (docs/PLAYER_API_CONTRACT.md).
 *
 * Deliberately not the app's `api` client: a player never holds a user
 * session. It authenticates with `X-Device-Token` only, talks to
 * `/api/v1/player/*`, and sees the same envelope every native client sees.
 */
import type { PreviewManifest } from "../preview/types";

const BASE = "/api/v1";

export class PlayerApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId: string | null,
  ) {
    super(message);
    this.name = "PlayerApiError";
  }
}

interface Envelope<T> {
  data: T;
  meta?: { request_id?: string };
  errors?: { code: string; message: string }[];
}

async function call<T>(
  method: string,
  path: string,
  body?: unknown,
  token?: string | null,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["X-Device-Token"] = token;
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let envelope: Envelope<T> | null;
  try {
    envelope = (await resp.json()) as Envelope<T>;
  } catch {
    envelope = null;
  }
  if (!resp.ok) {
    const err = envelope?.errors?.[0];
    throw new PlayerApiError(
      resp.status,
      err?.code ?? (resp.status === 429 ? "RATE_LIMITED" : "HTTP_ERROR"),
      err?.message ?? `${resp.status} ${resp.statusText}`,
      envelope?.meta?.request_id ?? null,
    );
  }
  return (envelope as Envelope<T>).data;
}

export interface RegisterInput {
  enrollment_key: string;
  serial_no: string;
  name?: string;
  manufacturer?: string;
  model?: string;
  platform?: string;
  os_version?: string;
  player_version?: string;
  screen_width?: number;
  screen_height?: number;
}

export interface RegisterResult {
  device_id: string;
  status: string;
  device_token: string | null;
}

export interface HeartbeatResult {
  acknowledged: boolean;
  heartbeat_interval_seconds: number;
  pending_commands: number;
  sync_required: boolean;
  update: { release_id: string; version?: string } | null;
}

export interface PlayerCommand {
  id: string;
  command_type: string;
  payload: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export type PlayerEvent =
  | {
      type: "playback";
      campaign_id: string | null;
      playlist_id: string | null;
      asset_id: string | null;
      started_at: string;
      ended_at: string;
      result: "completed" | "skipped" | "error" | "interrupted";
    }
  | { type: string; timestamp: string; payload?: Record<string, unknown> };

export const playerClient = {
  register: (input: RegisterInput) => call<RegisterResult>("POST", "/player/register", input),
  capabilities: (deviceId: string, token: string, capabilities: { code: string; supported: boolean; value?: Record<string, unknown> }[]) =>
    call<unknown>("POST", `/player/${deviceId}/capabilities`, { capabilities }, token),
  manifest: (deviceId: string, token: string) =>
    call<PreviewManifest>("GET", `/player/${deviceId}/manifest`, undefined, token),
  heartbeat: (deviceId: string, token: string, body: Record<string, unknown>) =>
    call<HeartbeatResult>("POST", `/player/${deviceId}/heartbeat`, body, token),
  ackDeployment: (deviceId: string, token: string, deploymentId: string, success = true, error?: string) =>
    call<unknown>("POST", `/player/${deviceId}/deployments/${deploymentId}/ack`, { success, error }, token),
  commands: (deviceId: string, token: string) =>
    call<PlayerCommand[]>("GET", `/player/${deviceId}/commands`, undefined, token),
  ackCommand: (deviceId: string, token: string, commandId: string, success: boolean, result?: Record<string, unknown>) =>
    call<PlayerCommand>("POST", `/player/${deviceId}/commands/${commandId}/ack`, { success, result }, token),
  events: (deviceId: string, token: string, events: PlayerEvent[]) =>
    call<{ stored_events: number; stored_playback: number }>("POST", `/player/${deviceId}/events`, { events }, token),
};
