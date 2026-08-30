import { Breadcrumb, Space, Typography } from "antd";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface Crumb {
  label: string;
  to?: string;
}

interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: Crumb[];
  /** Primary + secondary actions, right-aligned; wraps under the title
   * on narrow screens. */
  actions?: ReactNode;
}

/** Standard page header (brief §13): breadcrumb, title, description,
 * actions — one consistent structure for every business page. */
export function PageHeader({ title, description, breadcrumbs, actions }: PageHeaderProps) {
  return (
    <div className="mb-6">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumb
          className="mb-1"
          items={breadcrumbs.map((crumb) => ({
            title: crumb.to ? <Link to={crumb.to}>{crumb.label}</Link> : crumb.label,
          }))}
        />
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Typography.Title level={3} className="!mb-0">
            {title}
          </Typography.Title>
          {description && (
            <Typography.Text type="secondary">{description}</Typography.Text>
          )}
        </div>
        {actions && <Space wrap>{actions}</Space>}
      </div>
    </div>
  );
}
