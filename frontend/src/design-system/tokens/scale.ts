/**
 * Typography roles, spacing scale and breakpoints
 * (docs/design-system/DESIGN_TOKENS.md §2, §3, §6). These mirror antd's
 * own tokens so code can name a role instead of a number.
 */

/** Heading levels by role — the only levels the application uses. */
export const HEADING = {
  page: 3, // 24px, PageHeader only
  section: 4, // 20px, SectionCard / drawer sections
  card: 5, // 16px, cards and groups
} as const;

/** antd size scale in px, for the rare inline style that needs a number. */
export const SPACE = {
  xxs: 4,
  xs: 8,
  sm: 12,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

/** antd breakpoints (min-width, px). Use Grid.useBreakpoint() to read them. */
export const BREAKPOINTS = {
  xs: 0,
  sm: 576,
  md: 768,
  lg: 992,
  xl: 1200,
  xxl: 1600,
  xxxl: 1920,
} as const;

/** Standard responsive grid props (RESPONSIVE_COMPONENT_RULES.md). */
export const GRID = {
  gutter: [16, 16] as [number, number],
  cardGrid: { xs: 24, sm: 12, lg: 8, xl: 6 },
  mediaGrid: { xs: 12, sm: 8, lg: 6, xl: 4 },
  kpi: { xs: 12, sm: 8, xl: 4 },
  masterDetail: { xs: 24, lg: 15 },
  masterDetailSide: { xs: 24, lg: 9 },
  formPair: { xs: 24, md: 12 },
} as const;

/** Drawer widths by role (px); full width below `md` via EntityDrawer. */
export const DRAWER = {
  default: 480,
  wide: 640,
  filters: 400,
} as const;
