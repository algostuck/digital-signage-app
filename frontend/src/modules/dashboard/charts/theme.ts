import { theme } from "antd";
import {
  NEUTRAL_SERIES,
  SERIES_COLORS as DS_SERIES_COLORS,
  STATUS_TEXT,
  statusColor,
  statusLabel as dsStatusLabel,
  useThemeMode,
} from "@/design-system";

/**
 * Chart colours for the dashboard, derived from the design-system status
 * vocabulary and categorical palette — colour is never the only signal
 * on a chart (every series has a label and a text summary beside it).
 */
export const STATUS_COLORS = {
  online: statusColor("online", "device"),
  warning: statusColor("warning", "device"),
  offline: statusColor("offline", "device"),
  na: NEUTRAL_SERIES,
  completed: statusColor("completed"),
  failed: statusColor("failed"),
  plays: DS_SERIES_COLORS[0],
  acknowledged: statusColor("acknowledged"),
  pending: statusColor("pending"),
} as const;

export { STATUS_TEXT };

/** Ordered categorical palette for non-status series. */
export const SERIES_COLORS = DS_SERIES_COLORS;

export function useChartTheme() {
  const { mode } = useThemeMode();
  const { token } = theme.useToken();
  return {
    mode,
    /** G2 theme name; the view fill is overridden to sit on the card. */
    g2: mode === "dark" ? "classicDark" : "classic",
    viewStyle: { viewFill: "transparent" },
    text: token.colorTextSecondary,
    grid: mode === "dark" ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)",
    surface: token.colorBgContainer,
  };
}

export function statusLabel(key: string): string {
  return dsStatusLabel(key, "device");
}
