import type { ReactNode } from "react";
import { KpiCard } from "./KpiCard";

/**
 * Compatibility alias for the original StatCard API; new code uses
 * `KpiCard` (docs/design-system/COMPONENT_CATALOGUE.md). Kept so the
 * summary strips migrate one screen at a time without a big-bang rename.
 */
export function StatCard({
  label,
  value,
  icon,
  trend,
  context,
  tone,
  loading,
}: {
  label: string;
  value: number | string;
  icon?: ReactNode;
  trend?: number;
  context?: string;
  /** @deprecated use `tone` — arbitrary colours are not part of the system. */
  valueColor?: string;
  tone?: "success" | "warning" | "error";
  loading?: boolean;
}) {
  return (
    <KpiCard label={label} value={value} icon={icon} trend={trend} context={context} tone={tone} loading={loading} />
  );
}
