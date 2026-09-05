/**
 * Brand and layout seeds of the Digital Signage Cloud design system.
 * See docs/design-system/DESIGN_TOKENS.md §1 and §8.
 *
 * Change brand colour or semantics here only — never inline in a
 * component. Everything else derives from these through antd's
 * ConfigProvider (theme/buildTheme.ts).
 */

export type ThemeMode = "light" | "dark";

export const BRAND = {
  primary: "#1E40AF", // blue-800 — white text on it measures 8.6:1
  success: "#059669",
  warning: "#D97706",
  error: "#DC2626",
  info: "#0284C7",
} as const;

/** Sidebar surfaces, kept distinct from the page canvas in both modes. */
export const SIDEBAR_BG: Record<ThemeMode, string> = {
  light: "#FFFFFF",
  dark: "#0F172A",
};

/** Page canvas per mode (also painted on <body> by index.css). */
export const CANVAS_BG: Record<ThemeMode, string> = {
  light: "#F8FAFC",
  dark: "#0B1220",
};

/** Pill radius for status badges only — every other surface uses the
 * token-driven borderRadius scale. */
export const PILL_RADIUS = 9999;

/** Golden-ratio-inspired column splits for antd's 24-col grid, applied
 * selectively (major master–detail and dashboard splits) — not a
 * universal rule. */
export const GOLDEN_SPLIT = { primary: 15, secondary: 9 } as const;

/** Shell geometry (px). Header 55 ≈ φ × the 34px menu rows. */
export const SHELL = {
  siderWidth: 260,
  siderCollapsedWidth: 80,
  headerHeight: 55,
  contentMaxWidth: "clamp(1024px, 61.8cqw, 1440px)",
} as const;
