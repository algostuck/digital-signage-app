import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  InboxOutlined,
  InfoCircleOutlined,
  LockOutlined,
  MinusCircleOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  SyncOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { createElement, type ReactNode } from "react";
import { BRAND } from "./brand";
import type { Tone } from "./tone";

/**
 * The status vocabulary (docs/design-system/DESIGN_TOKENS.md §1).
 *
 * One table maps every backend status of every domain to a tone, an
 * icon and a label. `StatusBadge`, chart status series and any chip that
 * expresses state read from here. Adding a status means adding a row —
 * never a colour inside a page.
 */

export type StatusDomain =
  | "device"
  | "campaign"
  | "content"
  | "deployment"
  | "subscription"
  | "approval"
  | "schedule"
  | "user"
  | "severity"
  | "incident"
  | "generic";

export interface StatusMeta {
  tone: Tone;
  icon: ReactNode;
  label: string;
  /** Solid colour for chart series / dots (brand functional seed). */
  color: string;
}

const ok = (label: string): StatusMeta => ({
  tone: "success",
  icon: createElement(CheckCircleOutlined),
  label,
  color: BRAND.success,
});
const warn = (label: string, icon = ExclamationCircleOutlined): StatusMeta => ({
  tone: "warning",
  icon: createElement(icon),
  label,
  color: BRAND.warning,
});
const bad = (label: string, icon = CloseCircleOutlined): StatusMeta => ({
  tone: "error",
  icon: createElement(icon),
  label,
  color: BRAND.error,
});
const busy = (label: string): StatusMeta => ({
  tone: "processing",
  icon: createElement(SyncOutlined, { spin: true }),
  label,
  color: BRAND.info,
});
const info = (label: string, icon = InfoCircleOutlined): StatusMeta => ({
  tone: "processing",
  icon: createElement(icon),
  label,
  color: BRAND.info,
});
const off = (label: string, icon = MinusCircleOutlined): StatusMeta => ({
  tone: "default",
  icon: createElement(icon),
  label,
  color: "#94A3B8",
});
const high = (label: string): StatusMeta => ({
  tone: "high",
  icon: createElement(WarningOutlined),
  label,
  color: "#EA580C",
});

const GENERIC: Record<string, StatusMeta> = {
  active: ok("Active"),
  online: ok("Online"),
  ready: ok("Ready"),
  enabled: ok("Enabled"),
  connected: ok("Connected"),
  completed: ok("Completed"),
  confirmed: ok("Confirmed"),
  acknowledged: ok("Acknowledged"),
  healthy: ok("Healthy"),
  paid: ok("Paid"),
  success: ok("Success"),
  passed: ok("Passed"),
  valid: ok("Valid"),

  warning: warn("Warning"),
  pending: warn("Pending", ClockCircleOutlined),
  invited: warn("Invited", ClockCircleOutlined),
  paused: warn("Paused", PauseCircleOutlined),
  partial: warn("Partial"),
  stale: warn("Stale"),
  degraded: warn("Degraded"),
  flagged: warn("Flagged"),
  past_due: warn("Past due", ClockCircleOutlined),
  trial: warn("Trial", ClockCircleOutlined),
  returned: warn("Returned", EditOutlined),
  overdue: warn("Overdue", ClockCircleOutlined),
  open: warn("Open"),

  processing: busy("Processing"),
  publishing: busy("Publishing"),
  syncing: busy("Syncing"),
  updating: busy("Updating"),
  running: busy("Running"),
  uploading: busy("Uploading"),
  in_progress: busy("In progress"),
  queued: info("Queued", ClockCircleOutlined),
  scheduled: info("Scheduled", ClockCircleOutlined),
  info: info("Info"),
  live: { tone: "success", icon: createElement(PlayCircleOutlined), label: "Live", color: BRAND.success },

  offline: bad("Offline"),
  critical: bad("Critical"),
  rejected: bad("Rejected"),
  failed: bad("Failed"),
  error: bad("Error"),
  suspended: bad("Suspended"),
  revoked: bad("Revoked"),
  blocked: bad("Blocked"),
  expired_credential: bad("Expired"),

  high: high("High"),
  medium: warn("Medium"),
  low: off("Low"),

  deactivated: off("Deactivated"),
  disabled: off("Disabled"),
  decommissioned: off("Decommissioned"),
  draft: off("Draft", EditOutlined),
  archived: off("Archived", InboxOutlined),
  expired: off("Expired"),
  cancelled: off("Cancelled"),
  resolved: off("Resolved", CheckCircleOutlined),
  inactive: off("Inactive"),
  not_active: off("Not active"),
  na: off("Not active"),
  unknown: off("Unknown"),
  blackout: off("Blackout", LockOutlined),
};

/** Domain-specific overrides where the same word means something else. */
const DOMAIN_OVERRIDES: Partial<Record<StatusDomain, Record<string, StatusMeta>>> = {
  campaign: {
    pending_approval: warn("Pending approval", ClockCircleOutlined),
    approved: info("Approved", CheckCircleOutlined),
    published: ok("Published"),
  },
  approval: {
    pending: warn("Awaiting decision", ClockCircleOutlined),
    approved: ok("Approved"),
  },
  content: {
    published: ok("Published"),
    ready: ok("Ready"),
  },
  deployment: {
    published: ok("Published"),
    draft: off("Draft", EditOutlined),
    ready: info("Ready", CheckCircleOutlined),
  },
  device: {
    pending: warn("Pending approval", ClockCircleOutlined),
  },
  subscription: {
    active: ok("Active"),
    cancelled: off("Cancelled"),
  },
  schedule: {
    play: info("Play window", PlayCircleOutlined),
    conflict: bad("Conflict", WarningOutlined),
  },
  severity: {
    critical: bad("Critical"),
    high: high("High"),
    medium: warn("Medium"),
    low: off("Low"),
    info: info("Info"),
  },
};

const FALLBACK: StatusMeta = off("Unknown");

function humanize(status: string): string {
  return status
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");
}

/** Resolve a backend status string to its presentation. Unknown values
 * fall back to a neutral pill with a humanised label, never to nothing. */
export function statusMeta(status: string | null | undefined, domain: StatusDomain = "generic"): StatusMeta {
  if (!status) return FALLBACK;
  const key = status.toLowerCase();
  const override = DOMAIN_OVERRIDES[domain]?.[key];
  if (override) return override;
  const generic = GENERIC[key];
  if (generic) return generic;
  return { ...FALLBACK, label: humanize(key) };
}

export function statusLabel(status: string | null | undefined, domain: StatusDomain = "generic"): string {
  return statusMeta(status, domain).label;
}

export function statusTone(status: string | null | undefined, domain: StatusDomain = "generic"): Tone {
  return statusMeta(status, domain).tone;
}

/** Solid colour for a status series in a chart or a dot. */
export function statusColor(status: string | null | undefined, domain: StatusDomain = "generic"): string {
  return statusMeta(status, domain).color;
}
