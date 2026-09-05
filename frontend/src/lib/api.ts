/** API client implementing the standard envelope (docs/api-guidelines.md),
 *  with automatic single-flight access-token refresh. */

export interface ApiErrorItem {
  code: string;
  message: string;
  field?: string;
}

export interface ApiMeta {
  request_id?: string;
  page?: number;
  page_size?: number;
  total?: number;
}

export interface Envelope<T> {
  data: T | null;
  meta: ApiMeta;
  errors: ApiErrorItem[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public errors: ApiErrorItem[],
    public requestId?: string,
  ) {
    // Unexpected failures carry the request id in the message the UI shows,
    // so a screenshot of the toast is enough to find the server-side log
    // line ("ref 1a2b3c4d" -> request_id in the API and job logs).
    const base = errors[0]?.message ?? `Request failed (${status})`;
    super(status >= 500 && requestId ? `${base} (ref ${requestId.slice(0, 8)})` : base);
    this.name = "ApiError";
  }
  get code(): string {
    return this.errors[0]?.code ?? "INTERNAL_ERROR";
  }
}

const BASE = "/api/v1";
const REFRESH_STORAGE_KEY = "signage.refresh_token";

let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;
let onSessionExpired: (() => void) | null = null;

export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler;
}

export function setTokens(access: string | null, refresh: string | null) {
  accessToken = access;
  try {
    if (refresh) localStorage.setItem(REFRESH_STORAGE_KEY, refresh);
    else localStorage.removeItem(REFRESH_STORAGE_KEY);
  } catch {
    // Storage unavailable (private mode): session lives in memory only.
  }
}

export function getStoredRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_STORAGE_KEY);
  } catch {
    return null;
  }
}

async function rawRequest<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<{ resp: Response; envelope: Envelope<T> | null }> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const envelope = (await resp.json().catch(() => null)) as Envelope<T> | null;
  return { resp, envelope };
}

interface RefreshedSession {
  access_token: string;
  refresh_token: string;
  user: unknown;
}

/**
 * Refresh tokens are single-use: the server rotates them and treats a
 * second presentation of the same token as theft, revoking the whole
 * session family. So a refresh must never race — not within this tab
 * (React 18 double-runs effects in development) and not across tabs
 * (two tabs booting together read the same stored token). The Web Locks
 * API serialises across tabs of the origin; the token is re-read inside
 * the lock so a tab that waited picks up the one its sibling just wrote.
 */
async function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  const locks = (navigator as Navigator & { locks?: LockManager }).locks;
  if (locks?.request) return locks.request("dsc.session-refresh", fn);
  return fn();
}

async function rotate(): Promise<Envelope<RefreshedSession> | null> {
  return withRefreshLock(async () => {
    const stored = getStoredRefreshToken();
    if (!stored) return null;
    const { resp, envelope } = await rawRequest<RefreshedSession>("POST", "/auth/refresh", {
      refresh_token: stored,
    });
    if (!resp.ok || !envelope?.data) {
      setTokens(null, null);
      return null;
    }
    setTokens(envelope.data.access_token, envelope.data.refresh_token);
    return envelope;
  });
}

let restorePromise: Promise<Envelope<RefreshedSession> | null> | null = null;

/** Restores the session from the stored refresh token on app start.
 * Single-flight: concurrent callers share one request. */
export function restoreSession(): Promise<Envelope<RefreshedSession> | null> {
  if (!restorePromise) {
    restorePromise = rotate().finally(() => {
      restorePromise = null;
    });
  }
  return restorePromise;
}

/** Refreshes the access token once even under concurrent 401s. */
async function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = rotate()
      .then((envelope) => envelope != null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<Envelope<T>> {
  let { resp, envelope } = await rawRequest<T>(method, path, body);

  if (resp.status === 401 && !path.startsWith("/auth/")) {
    if (await tryRefresh()) {
      ({ resp, envelope } = await rawRequest<T>(method, path, body));
    } else {
      onSessionExpired?.();
    }
  }

  if (!resp.ok || !envelope) {
    throw new ApiError(
      resp.status,
      envelope?.errors ?? [{ code: "INTERNAL_ERROR", message: "Unexpected server response" }],
      envelope?.meta?.request_id,
    );
  }
  return envelope;
}

/** Fetches and saves the binary response as a file download (exports,
 * invoices). GET when body is undefined, POST otherwise. */
async function download(path: string, body?: unknown): Promise<void> {
  const doFetch = () =>
    fetch(`${BASE}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  let resp = await doFetch();
  if (resp.status === 401 && (await tryRefresh())) {
    resp = await doFetch();
  }
  if (!resp.ok) {
    const envelope = (await resp.json().catch(() => null)) as Envelope<unknown> | null;
    throw new ApiError(
      resp.status,
      envelope?.errors ?? [{ code: "INTERNAL_ERROR", message: "Export failed" }],
    );
  }
  const disposition = resp.headers.get("content-disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = match?.[1] ?? "report";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
  download,
};
