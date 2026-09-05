import { theme } from "antd";
import { BRAND } from "../../../theme/tokens";
import { useThemeMode } from "../../../theme/ThemeProvider";

/** Colour is never the only signal on a chart — every series also has a
 * label and a text summary beside it — but when colour is used it comes
 * from the app's semantic palette, not a chart library default. */
export const STATUS_COLORS = {
  online: BRAND.success,
  warning: BRAND.warning,
  offline: BRAND.error,
  na: "#94A3B8",
  completed: BRAND.success,
  failed: BRAND.error,
  plays: BRAND.primary,
  acknowledged: BRAND.success,
  pending: BRAND.warning,
} as const;

export { STATUS_TEXT } from "../../../components/ui/tone";

/** Ordered categorical palette for non-status series (content types,
 * campaign status). Six steps, all distinguishable on light and dark. */
export const SERIES_COLORS = [
  BRAND.primary,
  "#7C3AED",
  "#0891B2",
  "#D97706",
  "#059669",
  "#DB2777",
];

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
  switch (key) {
    case "na":
      return "Not active";
    case "online":
      return "Online";
    case "warning":
      return "Warning";
    case "offline":
      return "Offline";
    default:
      return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
  }
}
