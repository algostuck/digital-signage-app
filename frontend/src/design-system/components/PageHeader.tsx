import { Breadcrumb, Flex, Space, Typography } from "antd";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useBreadcrumbs, type Crumb } from "../patterns/breadcrumbs";
import { HEADING, SPACE } from "../tokens/scale";
import { useInsidePageContainer } from "./PageContainer";

export interface PageHeaderProps {
  title: string;
  description?: string;
  /**
   * Explicit trail (detail pages: `[{ label: "Campaigns", to: "/campaigns" }, { label: campaign.name }]`).
   * Omit to derive "Module › Page" from the navigation config; pass `[]`
   * to show none.
   */
  breadcrumbs?: Crumb[];
  /** Tags or badges beside the title (e.g. a StatusBadge). */
  extra?: ReactNode;
  /** Primary + secondary actions, right-aligned; wraps under the title
   * on narrow screens. Exactly one `type="primary"`. */
  actions?: ReactNode;
}

/**
 * Standard page header (docs/design-system/COMPONENT_CATALOGUE.md):
 * breadcrumb → title + description → actions. The title is the page's
 * single top-level heading (Typography level 3 = 24px).
 */
export function PageHeader({ title, description, breadcrumbs, extra, actions }: PageHeaderProps) {
  const derived = useBreadcrumbs();
  const inside = useInsidePageContainer();
  const trail = breadcrumbs ?? derived;
  return (
    <Flex vertical gap={4} component="header" style={inside ? undefined : { marginBottom: SPACE.lg }}>
      {trail.length > 0 && (
        <Breadcrumb
          items={trail.map((crumb, index) => ({
            title:
              crumb.to && index < trail.length - 1 ? <Link to={crumb.to}>{crumb.label}</Link> : crumb.label,
          }))}
        />
      )}
      <Flex wrap justify="space-between" align="flex-start" gap={12}>
        <Flex vertical gap={2} style={{ minWidth: 0 }}>
          <Flex align="center" gap={8} wrap>
            <Typography.Title level={HEADING.page}>{title}</Typography.Title>
            {extra}
          </Flex>
          {description && <Typography.Text type="secondary">{description}</Typography.Text>}
        </Flex>
        {actions && <Space wrap>{actions}</Space>}
      </Flex>
    </Flex>
  );
}
