import type { ThemeConfig } from "antd";

/**
 * Single source of truth for the design system's visual tokens.
 * See docs/UI_UX_DESIGN_SYSTEM.md for the rationale behind each value.
 * Change brand color / semantics here only — never override colors
 * ad hoc in a component.
 */
export const theme: ThemeConfig = {
  token: {
    colorPrimary: "#1D4ED8",
    colorSuccess: "#059669",
    colorWarning: "#D97706",
    colorError: "#DC2626",
    colorInfo: "#0284C7",
    colorLink: "#1D4ED8",

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
      siderBg: "#0F172A",
      headerBg: "#FFFFFF",
      bodyBg: "#F8FAFC",
    },
    Menu: {
      darkItemBg: "#0F172A",
      darkSubMenuItemBg: "#0F172A",
      darkItemSelectedBg: "#1D4ED8",
      darkItemHoverBg: "#1E293B",
    },
    Table: {
      headerBg: "#F8FAFC",
    },
    Card: {
      boxShadowTertiary: "0 1px 2px 0 rgba(15, 23, 42, 0.06)",
    },
  },
};

/** Pill radius for status badges only — every other surface uses the
 * token-driven borderRadius scale above. */
export const PILL_RADIUS = 9999;

/** Golden-ratio-inspired column splits for antd's 24-col grid, applied
 * selectively (docs/UI_UX_DESIGN_SYSTEM.md §1) — not a universal rule. */
export const GOLDEN_SPLIT = { primary: 15, secondary: 9 } as const;
