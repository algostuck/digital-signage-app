import { FallOutlined, RiseOutlined } from "@ant-design/icons";
import { Card, Statistic, Typography } from "antd";
import type { ReactNode } from "react";
import { useThemeMode } from "../theme/ThemeProvider";
import { STATUS_TEXT } from "../tokens/tone";

interface StatCardProps {
  label: string;
  value: number | string;
  icon?: ReactNode;
  /** Percentage change vs the previous period; sign picks the arrow. */
  trend?: number;
  /** Supporting context under the number ("vs previous period"). */
  context?: string;
  valueColor?: string;
  /** Status colour from the per-theme text palette (≥7:1); prefer over valueColor. */
  tone?: "success" | "warning" | "error";
  loading?: boolean;
}

/** KPI card (brief §15): label → large number → trend → context. */
export function StatCard({ label, value, icon, trend, context, valueColor, tone, loading }: StatCardProps) {
  const { mode } = useThemeMode();
  const color = tone ? STATUS_TEXT[mode][tone] : valueColor;
  return (
    <Card size="small" loading={loading}>
      <Statistic
        title={
          <span className="flex items-center gap-2">
            {icon}
            {label}
          </span>
        }
        value={value}
        styles={color ? { content: { color } } : undefined}
      />
      {(trend != null || context) && (
        <div className="mt-1 flex items-baseline gap-2">
          {trend != null && (
            <Typography.Text
              className={trend >= 0 ? "!text-emerald-600" : "!text-red-600"}
              strong
            >
              {trend >= 0 ? <RiseOutlined /> : <FallOutlined />} {Math.abs(trend)}%
            </Typography.Text>
          )}
          {context && (
            <Typography.Text type="secondary" className="text-xs">
              {context}
            </Typography.Text>
          )}
        </div>
      )}
    </Card>
  );
}
