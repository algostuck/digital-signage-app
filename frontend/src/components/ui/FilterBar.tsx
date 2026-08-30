import { ClearOutlined } from "@ant-design/icons";
import { Button, Space } from "antd";
import type { ReactNode } from "react";

interface FilterBarProps {
  children: ReactNode;
  onReset?: () => void;
}

/** Standard table/list filter row (brief §19): wraps on narrow screens,
 * optional Reset. Children are the page's own Search/Select/RangePicker
 * controls. */
export function FilterBar({ children, onReset }: FilterBarProps) {
  return (
    <Space wrap className="mb-4">
      {children}
      {onReset && (
        <Button icon={<ClearOutlined />} onClick={onReset}>
          Reset
        </Button>
      )}
    </Space>
  );
}
