import { Badge, Tag, Typography } from "antd";
import { cloneElement, isValidElement } from "react";
import { useThemeMode } from "../theme/ThemeProvider";
import { statusMeta, type StatusDomain } from "../tokens/status";
import { toneStyle } from "../tokens/tone";
import { useReducedMotion } from "../utilities/useReducedMotion";

export interface StatusBadgeProps {
  status: string | null | undefined;
  /** Domain vocabulary (device, campaign, deployment…); `generic` by default. */
  domain?: StatusDomain;
  /** Override the label from the vocabulary (rare — e.g. counts). */
  label?: string;
  size?: "small" | "medium";
  /** Dense lists: a status dot + text instead of a pill. */
  dot?: boolean;
}

/**
 * The one way to show a status (docs/design-system/COMPONENT_CATALOGUE.md):
 * tone + icon + label from the status vocabulary, so state is never
 * carried by colour alone and the same status looks the same on every
 * screen. Pass the raw backend value; the vocabulary supplies the words.
 */
export function StatusBadge({ status, domain = "generic", label, size = "medium", dot }: StatusBadgeProps) {
  const { mode } = useThemeMode();
  const reducedMotion = useReducedMotion();
  const meta = statusMeta(status, domain);
  const text = label ?? meta.label;
  // Processing statuses spin their icon; honour prefers-reduced-motion.
  const icon =
    reducedMotion && isValidElement<{ spin?: boolean }>(meta.icon) && meta.icon.props.spin
      ? cloneElement(meta.icon, { spin: false })
      : meta.icon;
  if (dot) {
    return (
      <Badge
        color={meta.color}
        text={<Typography.Text style={{ fontSize: size === "small" ? 12 : undefined }}>{text}</Typography.Text>}
      />
    );
  }
  return (
    <Tag
      icon={icon}
      style={{
        ...toneStyle(meta.tone, mode),
        marginInlineEnd: 0,
        ...(size === "small" ? { fontSize: 12, lineHeight: "18px", paddingInline: 6 } : {}),
      }}
    >
      {text}
    </Tag>
  );
}
