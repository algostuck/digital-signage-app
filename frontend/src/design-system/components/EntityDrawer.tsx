import { Drawer, Flex, Grid, Typography, type DrawerProps } from "antd";
import type { ReactNode } from "react";
import { DRAWER } from "../tokens/scale";

interface EntityDrawerProps extends Omit<DrawerProps, "title" | "size" | "width"> {
  title: ReactNode;
  /** Status pill or tags shown beside the title. */
  status?: ReactNode;
  /** One line under the title (type, location, id). */
  subtitle?: ReactNode;
  size?: "default" | "wide";
  children: ReactNode;
}

/**
 * Entity detail / contextual edit panel (docs/design-system/COMPONENT_CATALOGUE.md):
 * antd Drawer at 480 (default) or 640 (wide), full-width below `md`,
 * with a header of title + status + subtitle, `extra` actions and an
 * optional footer holding one primary action. Focus trap and return are
 * antd's.
 */
export function EntityDrawer({
  title,
  status,
  subtitle,
  size = "default",
  children,
  destroyOnHidden = true,
  placement = "right",
  ...drawer
}: EntityDrawerProps) {
  const screens = Grid.useBreakpoint();
  const compact = screens.md === false;
  return (
    <Drawer
      placement={placement}
      size={compact ? "100%" : size === "wide" ? DRAWER.wide : DRAWER.default}
      destroyOnHidden={destroyOnHidden}
      title={
        <Flex vertical gap={2} style={{ minWidth: 0 }}>
          <Flex align="center" gap={8} wrap>
            <Typography.Text strong ellipsis style={{ fontSize: 16 }}>
              {title}
            </Typography.Text>
            {status}
          </Flex>
          {subtitle && (
            <Typography.Text type="secondary" style={{ fontWeight: 400, fontSize: 13 }}>
              {subtitle}
            </Typography.Text>
          )}
        </Flex>
      }
      {...drawer}
    >
      {children}
    </Drawer>
  );
}
