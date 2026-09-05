import { FallOutlined, RiseOutlined } from "@ant-design/icons";
import { Card, Flex, Progress, Statistic, Typography, theme } from "antd";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useThemeMode } from "../theme/ThemeProvider";
import { STATUS_TEXT } from "../tokens/tone";

export interface KpiCardProps {
  label: string;
  value: number | string | ReactNode;
  icon?: ReactNode;
  /** Small text beside the value ("82%", "in progress"). */
  suffix?: ReactNode;
  /** Percentage change vs the previous period; sign picks the arrow. */
  trend?: number;
  /** Supporting context under the number ("vs previous 7 days"). */
  context?: ReactNode;
  /** Status colour for the value from the per-theme text palette (≥ 7:1). */
  tone?: "success" | "warning" | "error";
  /** Quota-style usage bar under the value (0–100). */
  progress?: number;
  loading?: boolean;
  /** Where the number leads with its filter applied; renders as a link card. */
  to?: string;
  /** For non-route actions (open a drawer, switch a filter). */
  onClick?: () => void;
}

/**
 * KPI card (docs/design-system/COMPONENT_CATALOGUE.md): metric → value →
 * trend → context on antd Card + Statistic. Every KPI has context; a
 * clickable card carries a full accessible name.
 */
export function KpiCard({
  label,
  value,
  icon,
  suffix,
  trend,
  context,
  tone,
  progress,
  loading,
  to,
  onClick,
}: KpiCardProps) {
  const { mode } = useThemeMode();
  const { token } = theme.useToken();
  const color = tone ? STATUS_TEXT[mode][tone] : undefined;
  const interactive = Boolean(to || onClick);

  const card = (
    <Card
      size="small"
      loading={loading}
      hoverable={interactive}
      style={{ height: "100%" }}
      styles={{ body: { padding: `${token.paddingSM}px ${token.padding}px` } }}
      onClick={onClick}
      tabIndex={onClick ? 0 : undefined}
      role={onClick ? "button" : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      <Statistic
        title={
          <Flex align="center" gap={token.marginXXS}>
            {icon && <span aria-hidden>{icon}</span>}
            <Typography.Text type="secondary" ellipsis style={{ fontSize: token.fontSizeSM, fontWeight: 500 }}>
              {label}
            </Typography.Text>
          </Flex>
        }
        value={typeof value === "number" || typeof value === "string" ? value : undefined}
        formatter={typeof value === "number" || typeof value === "string" ? undefined : () => value}
        suffix={
          suffix ? (
            <Typography.Text type="secondary" style={{ fontSize: token.fontSizeSM }}>
              {suffix}
            </Typography.Text>
          ) : undefined
        }
        styles={{ content: { color, fontVariantNumeric: "tabular-nums", fontWeight: 600 } }}
      />
      {typeof progress === "number" && (
        <Progress
          percent={Math.max(0, Math.min(100, progress))}
          size="small"
          showInfo={false}
          status={progress >= 100 ? "exception" : progress >= 80 ? "active" : "normal"}
          aria-label={`${label} usage ${Math.round(progress)}%`}
        />
      )}
      {(trend != null || context) && (
        <Flex align="baseline" gap={token.marginXS} wrap style={{ marginTop: token.marginXXS }}>
          {trend != null && (
            <Typography.Text strong style={{ color: STATUS_TEXT[mode][trend >= 0 ? "success" : "error"] }}>
              {trend >= 0 ? <RiseOutlined aria-hidden /> : <FallOutlined aria-hidden />}{" "}
              <span className="sr-only">{trend >= 0 ? "up" : "down"} </span>
              {Math.abs(trend)}%
            </Typography.Text>
          )}
          {context && (
            <Typography.Text type="secondary" ellipsis style={{ fontSize: token.fontSizeSM }}>
              {context}
            </Typography.Text>
          )}
        </Flex>
      )}
    </Card>
  );

  return to ? (
    <Link to={to} style={{ display: "block", height: "100%", textDecoration: "none" }} aria-label={`${label}: open details`}>
      {card}
    </Link>
  ) : (
    card
  );
}
