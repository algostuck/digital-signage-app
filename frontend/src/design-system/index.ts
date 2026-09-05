/**
 * Digital Signage Cloud design system — the one import for pages.
 *
 *   import { PageContainer, DataTable, StatusBadge, formatDate } from "@/design-system";
 *
 * Structure (docs/design-system/DESIGN_SYSTEM_USAGE.md):
 *   theme/       ConfigProvider theme + ThemeProvider (light/dark)
 *   tokens/      brand, tone palette, categorical palette, status vocabulary, scale
 *   components/  thin compositions over Ant Design
 *   patterns/    hooks that encode page-level conventions (breadcrumbs, responsive)
 *   utilities/   formatting, feedback, motion
 */

// theme
export { ThemeProvider, useThemeMode } from "./theme/ThemeProvider";
export { buildTheme } from "./theme/buildTheme";

// tokens
export { BRAND, CANVAS_BG, GOLDEN_SPLIT, PILL_RADIUS, SHELL, SIDEBAR_BG, type ThemeMode } from "./tokens/brand";
export { STATUS_TEXT, toneOf, toneStyle, type Tone } from "./tokens/tone";
export {
  HUES,
  NEUTRAL_SERIES,
  SERIES_COLORS,
  hueFor,
  hueStyle,
  mutedStripedStyle,
  seriesColor,
  type Hue,
} from "./tokens/palette";
export { statusColor, statusLabel, statusMeta, statusTone, type StatusDomain, type StatusMeta } from "./tokens/status";
export { BREAKPOINTS, DRAWER, GRID, HEADING, SPACE } from "./tokens/scale";

// patterns
export { BreadcrumbProvider, useBreadcrumbs, type BreadcrumbResolver, type Crumb } from "./patterns/breadcrumbs";

// components
export { PageHeader, type PageHeaderProps } from "./components/PageHeader";
export { PageContainer } from "./components/PageContainer";
export { ExceptionPage } from "./components/ExceptionPage";
export { ResponsiveActions, type SecondaryAction } from "./components/ResponsiveActions";
export { DataTable, type DataTableProps } from "./components/DataTable";
export { FilterBar } from "./components/FilterBar";
export { SearchBar } from "./components/SearchBar";
export { KpiCard, type KpiCardProps } from "./components/KpiCard";
export { StatCard } from "./components/StatCard";
export { StatusBadge, type StatusBadgeProps } from "./components/StatusBadge";
export { SectionCard } from "./components/SectionCard";
export { EntityDrawer } from "./components/EntityDrawer";
export { EntityList, type EntityListProps } from "./components/EntityList";
export { ConfirmAction } from "./components/ConfirmAction";
export { UploadArea } from "./components/UploadArea";
export { ChartFrame } from "./components/ChartFrame";
export { ToneTag } from "./components/ToneTag";
export { EmptyState, ErrorState, LoadingState } from "./components/states";
export { EntitlementGuard } from "./components/EntitlementGuard";

// utilities
export {
  EMPTY_VALUE,
  formatBytes,
  formatCompact,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatDayShort,
  formatDuration,
  formatFraction,
  formatNumber,
  formatPercent,
  formatRelative,
  formatTime,
} from "./utilities/format";
export { useFeedback } from "./utilities/feedback";
export { useReducedMotion } from "./utilities/useReducedMotion";
