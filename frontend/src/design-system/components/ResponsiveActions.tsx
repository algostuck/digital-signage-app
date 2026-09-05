import { MoreOutlined } from "@ant-design/icons";
import { Button, Dropdown, Grid, Space, type MenuProps } from "antd";
import type { ReactNode } from "react";

export interface SecondaryAction {
  key: string;
  label: string;
  icon?: ReactNode;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
}

/**
 * Action row that keeps the primary action visible everywhere and folds
 * the secondary actions into a "More" menu below `md`
 * (docs/design-system/RESPONSIVE_COMPONENT_RULES.md).
 */
export function ResponsiveActions({
  primary,
  secondary = [],
  size,
}: {
  primary?: ReactNode;
  secondary?: SecondaryAction[];
  size?: "small" | "medium" | "large";
}) {
  const screens = Grid.useBreakpoint();
  const compact = screens.md === false;
  if (!compact || secondary.length === 0) {
    return (
      <Space wrap size="small">
        {secondary.map((action) => (
          <Button
            key={action.key}
            size={size}
            icon={action.icon}
            danger={action.danger}
            disabled={action.disabled}
            onClick={action.onClick}
          >
            {action.label}
          </Button>
        ))}
        {primary}
      </Space>
    );
  }
  const items: MenuProps["items"] = secondary.map((action) => ({
    key: action.key,
    label: action.label,
    icon: action.icon,
    danger: action.danger,
    disabled: action.disabled,
    onClick: action.onClick,
  }));
  return (
    <Space size="small">
      {primary}
      <Dropdown menu={{ items }} trigger={["click"]} placement="bottomRight">
        <Button size={size} icon={<MoreOutlined />} aria-label="More actions" />
      </Dropdown>
    </Space>
  );
}
