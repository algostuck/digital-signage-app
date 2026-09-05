import { theme as antdTheme, type ThemeConfig } from "antd";
import { BRAND, SHELL, SIDEBAR_BG, type ThemeMode } from "../tokens/brand";

export type { ThemeMode } from "../tokens/brand";

/**
 * The single ConfigProvider theme of the application
 * (docs/design-system/DESIGN_TOKENS.md). Seeds come from tokens/brand.ts;
 * text aliases are deliberately stronger than antd's defaults so body and
 * secondary copy clear WCAG 2.2 **AAA** (7:1) in both modes.
 *
 * Both the light and dark menu key sets are always supplied — the Menu
 * picks by its own `theme` prop. Swapping which *keys* exist per mode
 * leaves stale cssinjs rules behind when the user toggles the theme at
 * runtime.
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
      // Danger text and buttons: red-800 clears 7:1 on white; the dark
      // algorithm derives its own tints from the brand red.
      colorError: dark ? BRAND.error : "#991B1B",
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
      colorTextTertiary: dark ? "rgba(255, 255, 255, 0.72)" : "#475569",
      // Placeholders double as the visible label of cleared filters, so they
      // are held to the same 7:1 as secondary text rather than antd's 1.8:1.
      colorTextPlaceholder: dark ? "rgba(255, 255, 255, 0.72)" : "#475569",
      // Status-coloured *text* (Typography type="success|warning|danger",
      // Statistic value styles). The brand status seeds are tuned for fills
      // and measure 3.8–4.5:1 as text; these shades clear 7:1 in each mode.
      colorSuccessText: dark ? "#4ADE80" : "#065F46",
      colorWarningText: dark ? "#FBBF24" : "#92400E",
      colorErrorText: dark ? "#FCA5A5" : "#991B1B",

      colorBgLayout: dark ? "#0B1220" : "#F8FAFC",
      // Dark surfaces stay in the same navy family as the canvas and the
      // sidebar; antd's stock neutral greys read as a different palette
      // sitting on top of the app. Both are darker than the defaults, so
      // every measured contrast ratio improves.
      ...(dark ? { colorBgContainer: "#111A2E", colorBgElevated: "#16203A" } : {}),

      fontFamily:
        '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      fontSize: 14,
      // Typography roles (DESIGN_TOKENS.md §2): page 24, section 20,
      // card 16. Levels 1–2 exist for antd's defaults but are not used
      // by the application.
      fontSizeHeading3: 24,
      fontSizeHeading4: 20,
      fontSizeHeading5: 16,

      borderRadius: 8,
      borderRadiusSM: 4,
      borderRadiusLG: 12,

      controlHeight: 32,
      wireframe: false,
    },
    components: {
      // Dark surfaces: danger buttons and the active page number keep their
      // meaning but pick text/bg pairs that clear 7:1 on the dark card
      // (the brand red measures 2.9:1 there; the derived primary 1.7:1).
      Button: dark ? { colorError: "#FCA5A5", dangerColor: "#450A0A" } : {},
      Pagination: dark ? { colorPrimary: "#93C5FD", itemActiveBg: "#172554" } : {},
      Layout: {
        // Matches the sidebar's logo and account bands so the three top
        // edges line up, and sits at φ against the 34px menu rows.
        headerHeight: SHELL.headerHeight,
        siderBg: SIDEBAR_BG[mode],
        headerBg: dark ? "#0F172A" : "#FFFFFF",
        bodyBg: dark ? "#0B1220" : "#F8FAFC",
      },
      Menu: {
        ...MENU_TOKENS,
        // Light-variant menus inside the content area (folder trees, tab
        // rails) sit on the dark card in dark mode; the sidebar uses the
        // dark variant and is unaffected.
        itemColor: dark ? "rgba(255, 255, 255, 0.85)" : MENU_TOKENS.itemColor,
        itemSelectedBg: dark ? "#172554" : MENU_TOKENS.itemSelectedBg,
        itemSelectedColor: dark ? "#BFDBFE" : MENU_TOKENS.itemSelectedColor,
        itemHoverBg: dark ? "rgba(255, 255, 255, 0.06)" : MENU_TOKENS.itemHoverBg,
        itemHoverColor: dark ? "#FFFFFF" : MENU_TOKENS.itemHoverColor,
        // Golden rhythm: 34px rows against the 55px logo, header and
        // account bands (55 / 34 = 1.618). Fibonacci steps throughout —
        // 13px type, 21px submenu indent — keep the rail compact without
        // crowding: 34px still clears the 24px minimum target size.
        itemHeight: 34,
        itemMarginBlock: 1,
        itemMarginInline: 4,
        itemPaddingInline: 12,
        itemBorderRadius: 8,
        iconSize: 16,
        collapsedIconSize: 18,
        fontSize: 13,
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
      Typography: {
        // Titles carry their own spacing from PageHeader / SectionCard;
        // a bottom margin on every heading forced 30 `!mb-0` overrides.
        titleMarginBottom: 0,
        titleMarginTop: 0,
      },
    },
  };
}
