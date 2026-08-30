import { ToolOutlined } from "@ant-design/icons";
import { Result } from "antd";

interface Props {
  title: string;
  milestone: string;
}

/** Route stub for modules whose backend slice is not implemented yet.
 *  Replaced with real screens as each vertical slice lands — never shipped
 *  with mock data. */
export function PlaceholderPage({ title, milestone }: Props) {
  return (
    <Result
      icon={<ToolOutlined />}
      title={title}
      subTitle={`This module is scheduled for milestone ${milestone}. It will be built as a vertical slice (API first, then UI) — see docs/development-plan.md.`}
    />
  );
}
