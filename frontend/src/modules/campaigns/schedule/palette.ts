import {
  hueFor,
  hueStyle,
  mutedStripedStyle,
  statusLabel as dsStatusLabel,
  statusTone as dsStatusTone,
  type ThemeMode,
  type Tone,
} from "@/design-system";
import type { CSSProperties } from "react";
import type { ConflictReason, ConflictSeverity } from "../types";

/**
 * Schedule-workspace vocabulary, expressed entirely through the design
 * system (docs/design-system/DESIGN_TOKENS.md): campaign hues come from
 * the categorical palette, statuses and severities from the status
 * vocabulary. Nothing here declares a colour.
 */

export const campaignHue = hueFor;

/** Fill + text + left bar for a play window of this campaign. */
export function campaignStyle(campaignId: string, mode: ThemeMode): CSSProperties {
  return hueStyle(campaignId, mode);
}

/** Blackouts are muted and striped, never a campaign colour. */
export function blackoutStyle(mode: ThemeMode): CSSProperties {
  return mutedStripedStyle(mode);
}

export const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  ["draft", "pending_approval", "approved", "published", "paused", "expired", "archived"].map((s) => [
    s,
    dsStatusLabel(s, "campaign"),
  ]),
);

export function statusTone(status: string | null | undefined): Tone {
  return dsStatusTone(status, "campaign");
}

export function statusLabel(status: string | null | undefined): string {
  return status ? dsStatusLabel(status, "campaign") : "Unknown";
}

export function severityTone(severity: ConflictSeverity): Tone {
  return dsStatusTone(severity, "severity");
}

export const SEVERITY_LABEL: Record<ConflictSeverity, string> = {
  high: dsStatusLabel("high", "severity"),
  medium: dsStatusLabel("medium", "severity"),
  low: dsStatusLabel("low", "severity"),
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
