import type { CSSProperties } from "react";
import type { Tone } from "@/design-system";
import type { ThemeMode } from "@/design-system";
import type { ConflictReason, ConflictSeverity } from "../types";

/**
 * Deterministic campaign colours and the status / severity vocabulary of
 * the schedule workspace.
 *
 * Every pair is a Tailwind 100/900 (light) or 900/100 (dark) combination,
 * which measures ≥ 9:1 for text on its own fill in both themes; the
 * `bar` shade (700) is the left border and legend swatch. Colour is a
 * secondary cue only — every chip also carries its text, an icon for
 * blackouts / conflicts / recurrence, and an accessible name.
 */

interface Hue {
  light: { bg: string; fg: string };
  dark: { bg: string; fg: string };
  bar: string;
}

const HUES: Hue[] = [
  { light: { bg: "#DBEAFE", fg: "#1E3A8A" }, dark: { bg: "#1E3A8A", fg: "#BFDBFE" }, bar: "#1D4ED8" },
  { light: { bg: "#CCFBF1", fg: "#134E4A" }, dark: { bg: "#134E4A", fg: "#99F6E4" }, bar: "#0F766E" },
  { light: { bg: "#EDE9FE", fg: "#4C1D95" }, dark: { bg: "#4C1D95", fg: "#DDD6FE" }, bar: "#6D28D9" },
  { light: { bg: "#FEF3C7", fg: "#78350F" }, dark: { bg: "#78350F", fg: "#FDE68A" }, bar: "#B45309" },
  { light: { bg: "#FFE4E6", fg: "#881337" }, dark: { bg: "#881337", fg: "#FECDD3" }, bar: "#BE123C" },
  { light: { bg: "#D1FAE5", fg: "#064E3B" }, dark: { bg: "#064E3B", fg: "#A7F3D0" }, bar: "#047857" },
  { light: { bg: "#E0F2FE", fg: "#0C4A6E" }, dark: { bg: "#0C4A6E", fg: "#BAE6FD" }, bar: "#0369A1" },
  { light: { bg: "#FAE8FF", fg: "#701A75" }, dark: { bg: "#701A75", fg: "#F5D0FE" }, bar: "#A21CAF" },
];

function hashId(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return hash;
}

export function campaignHue(campaignId: string): Hue {
  return HUES[hashId(campaignId) % HUES.length];
}

/** Fill + text + left bar for a play window of this campaign. */
export function campaignStyle(campaignId: string, mode: ThemeMode): CSSProperties {
  const hue = campaignHue(campaignId);
  return {
    background: hue[mode].bg,
    color: hue[mode].fg,
    borderLeft: `4px solid ${hue.bar}`,
  };
}

/** Blackouts are muted and striped, never a campaign colour. */
export function blackoutStyle(mode: ThemeMode): CSSProperties {
  const stripe = mode === "dark" ? "rgba(148,163,184,0.22)" : "rgba(100,116,139,0.18)";
  return {
    background: `repeating-linear-gradient(135deg, transparent 0 6px, ${stripe} 6px 9px), ${
      mode === "dark" ? "#1E293B" : "#F1F5F9"
    }`,
    color: mode === "dark" ? "#E2E8F0" : "#1E293B",
    borderLeft: `4px solid ${mode === "dark" ? "#94A3B8" : "#64748B"}`,
  };
}

export const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  pending_approval: "Pending approval",
  approved: "Approved",
  published: "Published",
  paused: "Paused",
  expired: "Expired",
  archived: "Archived",
};

export function statusTone(status: string | null | undefined): Tone {
  switch (status) {
    case "published":
      return "success";
    case "approved":
      return "processing";
    case "pending_approval":
    case "paused":
      return "warning";
    default:
      return "default";
  }
}

export function statusLabel(status: string | null | undefined): string {
  return status ? (STATUS_LABEL[status] ?? status) : "Unknown";
}

export function severityTone(severity: ConflictSeverity): Tone {
  if (severity === "high") return "error";
  if (severity === "medium") return "warning";
  return "default";
}

export const SEVERITY_LABEL: Record<ConflictSeverity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const REASON_LABEL: Record<ConflictReason, string> = {
  equal_priority_shared_screens: "Equal priority on shared screens",
  shadowed_by_priority: "Never plays — covered by a higher priority",
  inside_blackout: "Play window inside its own blackout",
};

export const PRIORITY_BANDS = [
  { value: "", label: "Any priority" },
  { value: "70-100", label: "High (70–100)" },
  { value: "40-69", label: "Medium (40–69)" },
  { value: "1-39", label: "Low (1–39)" },
] as const;
