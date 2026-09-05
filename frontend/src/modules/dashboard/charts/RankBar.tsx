import { Button, Progress, Typography } from "antd";
import type { ReactNode } from "react";

export interface RankRow {
  key: string;
  label: ReactNode;
  sublabel?: ReactNode;
  value: number;
  /** Shown instead of the raw value when set (e.g. "98.4%"). */
  display?: string;
  color?: string;
  href?: string;
  onClick?: () => void;
}

/** Ranked list with proportional bars. A list, not a chart: rankings read
 * best as rows with numbers, and antd's Progress already does the bar. */
export function RankBar({ rows, max, ariaLabel }: { rows: RankRow[]; max?: number; ariaLabel: string }) {
  const top = max ?? Math.max(1, ...rows.map((r) => r.value));
  return (
    <ol className="m-0 list-none p-0" aria-label={ariaLabel}>
      {rows.map((row, index) => {
        const inner = (
          <>
            <div className="flex items-baseline gap-2">
              <Typography.Text type="secondary" className="w-5 shrink-0 tabular-nums text-xs">
                {index + 1}
              </Typography.Text>
              <div className="min-w-0 flex-1">
                <Typography.Text ellipsis className="block">
                  {row.label}
                </Typography.Text>
                {row.sublabel && (
                  <Typography.Text type="secondary" className="block truncate text-xs">
                    {row.sublabel}
                  </Typography.Text>
                )}
              </div>
              <Typography.Text strong className="shrink-0 tabular-nums">
                {row.display ?? row.value.toLocaleString()}
              </Typography.Text>
            </div>
            <Progress
              percent={Math.round((row.value / top) * 100)}
              showInfo={false}
              size={["100%", 6]}
              strokeColor={row.color}
              className="!mb-0 !mt-1"
              aria-hidden
            />
          </>
        );
        return (
          <li key={row.key} className="py-1.5">
            {row.onClick ? (
              <Button
                type="text"
                block
                onClick={row.onClick}
                style={{ height: "auto", display: "block", paddingInline: 4, paddingBlock: 4, textAlign: "left" }}
              >
                {inner}
              </Button>
            ) : (
              <div className="px-1">{inner}</div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
