import { theme as antdTheme, type ThemeConfig } from "antd";

export type ThemeMode = "light" | "dark";

/**
 * Single source of truth for the design system's visual tokens.
 * See docs/UI_UX_DESIGN_SYSTEM.md for the rationale behind each value.
 * Change brand colour / semantics here only — never override colours ad
 * hoc in a component.
 *
 * Text tokens are deliberately stronger than antd's defaults so body and
 * secondary copy clear WCAG 2.2 **AAA** (7:1) rather than just AA, in
 * both modes.
 */
const BRAND = {
  primary: "#1D4ED8", // blue-700
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

/**
 * Both the light and dark menu key sets are always supplied — the Menu
 * picks by its own `theme` prop. Swapping which *keys* exist per mode
 * leaves stale cssinjs rules behind when the user toggles the theme at
 * runtime, which showed up as the sidebar keeping the previous theme's
 * colours until a reload.
 */
const MENU_TOKENS = {
  // Light menu
  itemSelectedBg: "#DBEAFE", // blue-100 — pairs with blue-900 text
  itemSelectedColor: "#1E3A8A", // blue-900
  itemColor: "#334155", // slate-700, 10.9:1 on white
  itemHoverBg: "#F1F5F9",
  itemHoverColor: "#0F172A",
  // Dark menu
  darkItemBg: "transparent",
  darkSubMenuItemBg: "transparent",
  darkPopupBg: SIDEBAR_BG.dark,
  // blue-800 rather than the brand blue-700: white on this reaches AAA
  // (8.7:1) without changing the brand colour anywhere else.
  darkItemSelectedBg: "#1E40AF",
  darkItemSelectedColor: "#FFFFFF",
  darkItemHoverBg: "#1E293B",
  darkItemColor: "rgba(255, 255, 255, 0.75)",
} as const;

export function buildTheme(mode: ThemeMode): ThemeConfig {
  const dark = mode === "dark";
  return {
    algorithm: dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      colorPrimary: BRAND.primary,
      colorSuccess: BRAND.success,
      colorWarning: BRAND.warning,
      colorError: BRAND.error,
      colorInfo: BRAND.info,
      // Link/emphasis text needs to clear 7:1 against the page canvas, so
      // it cannot be the brand blue in either mode: blue-800 on light,
      // blue-300 on dark. Solid primary surfaces keep BRAND.primary.
      colorLink: dark ? "#93C5FD" : "#1E40AF",

      // AAA-grade body/secondary text in both modes. `colorTextDescription`
      // is what Typography's `type="secondary"` actually resolves to, so it
      // has to be raised alongside colorTextSecondary or muted copy lands
      // at ~6.9:1 — just under AAA.
      colorText: dark ? "rgba(255, 255, 255, 0.92)" : "#0F172A",
      colorTextSecondary: dark ? "rgba(255, 255, 255, 0.75)" : "#475569",
      colorTextDescription: dark ? "rgba(255, 255, 255, 0.75)" : "#475569",
      colorTextTertiary: dark ? "rgba(255, 255, 255, 0.65)" : "#64748B",

      colorBgLayout: dark ? "#0B1220" : "#F8FAFC",

      fontFamily:
        '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      fontSize: 14,

      borderRadius: 8,
      borderRadiusSM: 4,
      borderRadiusLG: 12,

      controlHeight: 32,
      wireframe: false,
    },
    components: {
      Layout: {
        siderBg: SIDEBAR_BG[mode],
        headerBg: dark ? "#0F172A" : "#FFFFFF",
        headerHeight: 64,
        bodyBg: dark ? "#0B1220" : "#F8FAFC",
      },
      Menu: {
        ...MENU_TOKENS,
        // 8pt rhythm: 40px rows sit at 1:1.6 against the 64px logo and
        // account bands, and a 16px icon column aligns with the brand mark.
        itemHeight: 40,
        itemMarginBlock: 2,
        itemMarginInline: 4,
        itemPaddingInline: 12,
        itemBorderRadius: 8,
        iconSize: 16,
        collapsedIconSize: 18,
      },
      Tabs: {
        // The brand blue is too dark to read as text on the dark canvas.
        itemSelectedColor: dark ? "#93C5FD" : "#1E40AF",
        inkBarColor: dark ? "#93C5FD" : "#1E40AF",
        itemColor: dark ? "rgba(255, 255, 255, 0.75)" : "#475569",
        itemHoverColor: dark ? "#BFDBFE" : "#1E3A8A",
      },
      Table: {
        headerBg: dark ? "#111A2E" : "#F8FAFC",
      },
      Card: {
        boxShadowTertiary: dark ? "none" : "0 1px 2px 0 rgba(15, 23, 42, 0.06)",
      },
    },
  };
}

/** Pill radius for status badges only — every other surface uses the
 * token-driven borderRadius scale above. */
export const PILL_RADIUS = 9999;

/** Golden-ratio-inspired column splits for antd's 24-col grid, applied
 * selectively (docs/UI_UX_DESIGN_SYSTEM.md §1) — not a universal rule. */
export const GOLDEN_SPLIT = { primary: 15, secondary: 9 } as const;
