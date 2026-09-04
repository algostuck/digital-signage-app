import type { CSSProperties } from "react";
import type { ThemeMode } from "../../theme/tokens";

export type Tone = "success" | "warning" | "error" | "processing" | "default" | "high";

/**
 * Tinted-pill colours for status and severity tags, per theme.
 *
 * antd's `variant="filled"` tag pairs a pale background with a mid-tone
 * text colour that measures 2.9–5.6:1 in dark mode — below AA for
 * "Critical" and "Medium". These pairs are chosen so the text clears 7:1
 * on its own pill in both modes (measured with the canvas-composited
 * contrast check used across the app), while keeping the familiar
 * tinted look. Colour is never the only signal — every tag also carries
 * an icon or its own label text.
 */
const PALETTE: Record<Tone, Record<ThemeMode, { bg: string; fg: string }>> = {
  success: { light: { bg: "#DCFCE7", fg: "#14532D" }, dark: { bg: "#14532D", fg: "#BBF7D0" } },
  warning: { light: { bg: "#FEF3C7", fg: "#78350F" }, dark: { bg: "#451A03", fg: "#FDE68A" } },
  error: { light: { bg: "#FEE2E2", fg: "#7F1D1D" }, dark: { bg: "#450A0A", fg: "#FECACA" } },
  high: { light: { bg: "#FFEDD5", fg: "#7C2D12" }, dark: { bg: "#431407", fg: "#FED7AA" } },
  processing: { light: { bg: "#DBEAFE", fg: "#1E3A8A" }, dark: { bg: "#172554", fg: "#BFDBFE" } },
  default: { light: { bg: "#F1F5F9", fg: "#1E293B" }, dark: { bg: "#1E293B", fg: "#E2E8F0" } },
};

export function toneStyle(tone: Tone, mode: ThemeMode): CSSProperties {
  const { bg, fg } = PALETTE[tone][mode];
  return { background: bg, color: fg, borderColor: "transparent" };
}
