import type { CSSProperties } from "react";
import { BRAND, type ThemeMode } from "./brand";

/**
 * Categorical palette (docs/design-system/DESIGN_TOKENS.md §1): eight
 * hues for chart series and campaign colours. Every pair is a Tailwind
 * 100/900 (light) or 900/100 (dark) combination, ≥ 9:1 for text on its
 * own fill; `bar` (700) is the stroke / border / legend swatch.
 * Colour is always a secondary cue — every chip also carries text and,
 * where it matters, an icon.
 */
export interface Hue {
  name: string;
  light: { bg: string; fg: string };
  dark: { bg: string; fg: string };
  bar: string;
}

export const HUES: readonly Hue[] = [
  { name: "blue", light: { bg: "#DBEAFE", fg: "#1E3A8A" }, dark: { bg: "#1E3A8A", fg: "#BFDBFE" }, bar: "#1D4ED8" },
  { name: "teal", light: { bg: "#CCFBF1", fg: "#134E4A" }, dark: { bg: "#134E4A", fg: "#99F6E4" }, bar: "#0F766E" },
  { name: "violet", light: { bg: "#EDE9FE", fg: "#4C1D95" }, dark: { bg: "#4C1D95", fg: "#DDD6FE" }, bar: "#6D28D9" },
  { name: "amber", light: { bg: "#FEF3C7", fg: "#78350F" }, dark: { bg: "#78350F", fg: "#FDE68A" }, bar: "#B45309" },
  { name: "rose", light: { bg: "#FFE4E6", fg: "#881337" }, dark: { bg: "#881337", fg: "#FECDD3" }, bar: "#BE123C" },
  { name: "emerald", light: { bg: "#D1FAE5", fg: "#064E3B" }, dark: { bg: "#064E3B", fg: "#A7F3D0" }, bar: "#047857" },
  { name: "sky", light: { bg: "#E0F2FE", fg: "#0C4A6E" }, dark: { bg: "#0C4A6E", fg: "#BAE6FD" }, bar: "#0369A1" },
  { name: "fuchsia", light: { bg: "#FAE8FF", fg: "#701A75" }, dark: { bg: "#701A75", fg: "#F5D0FE" }, bar: "#A21CAF" },
];

/** Ordered series colours for charts: brand first, then the hue bars. */
export const SERIES_COLORS: readonly string[] = [
  BRAND.primary,
  HUES[2].bar,
  HUES[6].bar,
  HUES[3].bar,
  HUES[5].bar,
  HUES[4].bar,
  HUES[1].bar,
  HUES[7].bar,
];

export function seriesColor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}

function hashId(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return hash;
}

/** Deterministic hue for an entity id (campaigns, playlists…). */
export function hueFor(id: string): Hue {
  return HUES[hashId(id) % HUES.length];
}

/** Fill + text + left bar for a coloured chip or block of this entity. */
export function hueStyle(id: string, mode: ThemeMode): CSSProperties {
  const hue = hueFor(id);
  return {
    background: hue[mode].bg,
    color: hue[mode].fg,
    borderLeft: `4px solid ${hue.bar}`,
  };
}

/** Muted, striped fill for suppressed / blackout blocks — never a hue. */
export function mutedStripedStyle(mode: ThemeMode): CSSProperties {
  const stripe = mode === "dark" ? "rgba(148,163,184,0.22)" : "rgba(100,116,139,0.18)";
  return {
    background: `repeating-linear-gradient(135deg, transparent 0 6px, ${stripe} 6px 9px), ${
      mode === "dark" ? "#1E293B" : "#F1F5F9"
    }`,
    color: mode === "dark" ? "#E2E8F0" : "#1E293B",
    borderLeft: `4px solid ${mode === "dark" ? "#94A3B8" : "#64748B"}`,
  };
}

/** Neutral "not applicable" colour for charts. */
export const NEUTRAL_SERIES = "#94A3B8";
