import { Card, Flex, Typography, type CardProps } from "antd";
import type { ReactNode } from "react";
import { HEADING } from "../tokens/scale";

interface SectionCardProps extends Omit<CardProps, "title" | "extra" | "actions"> {
  title?: ReactNode;
  /** One sentence under the title saying what the section is for. */
  description?: ReactNode;
  /** Section-level actions, top right. */
  actions?: ReactNode;
  /** Heading level: `section` (h4, 20px) on pages, `card` (h5, 16px)
   * inside drawers and nested groups — keeps heading order valid. */
  level?: "section" | "card";
  children: ReactNode;
}

/**
 * A titled section (docs/design-system/COMPONENT_CATALOGUE.md): the same
 * header (title, description, actions) on every settings section, detail
 * group and dashboard panel. One topic per card; nest at most twice.
 */
export function SectionCard({
  title,
  description,
  actions,
  level = "section",
  children,
  size = "medium",
  ...card
}: SectionCardProps) {
  const heading = level === "section" ? HEADING.section : HEADING.card;
  return (
    <Card
      size={size}
      {...card}
      title={
        title ? (
          <Flex vertical gap={2} style={{ paddingBlock: 4, whiteSpace: "normal" }}>
            <Typography.Title level={heading}>{title}</Typography.Title>
            {description && (
              <Typography.Text type="secondary" style={{ fontWeight: 400 }}>
                {description}
              </Typography.Text>
            )}
          </Flex>
        ) : undefined
      }
      extra={actions}
    >
      {children}
    </Card>
  );
}
