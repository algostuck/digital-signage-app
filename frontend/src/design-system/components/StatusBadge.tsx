import { Badge, Tag, Typography } from "antd";
import { useThemeMode } from "../theme/ThemeProvider";
import { statusMeta, type StatusDomain } from "../tokens/status";
import { toneStyle } from "../tokens/tone";

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
  const meta = statusMeta(status, domain);
  const text = label ?? meta.label;
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
      icon={meta.icon}
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
