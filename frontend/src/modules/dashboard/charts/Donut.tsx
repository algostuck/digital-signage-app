import { Pie } from "@ant-design/plots";
import { Typography } from "antd";
import { useMemo, useRef } from "react";
import { useChartTheme } from "./theme";
import { ChartHost } from "./ChartHost";

export interface DonutSlice {
  key: string;
  label: string;
  value: number;
  color: string;
}

/** Status-mix donut. Every slice carries a label and a value in the
 * legend list beside it, so the colours are reinforcement only. Clicking a
 * slice (or its legend row) drills into that status. The G2 config is
 * memoised on the slice data; the click handler goes through a ref so the
 * config never changes identity because of it. */
export function Donut({
  slices,
  centre,
  centreLabel,
  onSelect,
  height = 200,
}: {
  slices: DonutSlice[];
  centre?: string | number;
  centreLabel?: string;
  onSelect?: (key: string) => void;
  height?: number;
}) {
  const chart = useChartTheme();
  const total = slices.reduce((n, s) => n + s.value, 0);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  const signature = JSON.stringify(slices);

  const config = useMemo(() => {
    const data = slices.filter((s) => s.value > 0);
    return {
      data,
      angleField: "value",
      colorField: "label",
      innerRadius: 0.7,
      height,
      autoFit: true,
      animate: false,
      legend: false,
      label: false,
      theme: chart.g2,
      viewStyle: chart.viewStyle,
      scale: { color: { range: data.map((s) => s.color) } },
      style: { stroke: chart.surface, lineWidth: 2 },
      onEvent: (_chart: unknown, event: { type: string; data?: { data?: DonutSlice } }) => {
        if (event.type === "element:click" && selectRef.current) {
          const label = event.data?.data?.label;
          const slice = slices.find((s) => s.label === label);
          if (slice) selectRef.current(slice.key);
        }
      },
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, height, chart.g2, chart.surface]);

  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="relative min-w-[180px] flex-1" style={{ height }} aria-hidden>
        <ChartHost height={height}>
          <Pie {...config} />
        </ChartHost>
        {centre !== undefined && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <Typography.Text strong style={{ fontSize: 26, lineHeight: 1.1 }}>
              {centre}
            </Typography.Text>
            {centreLabel && (
              <Typography.Text type="secondary" className="text-xs">
                {centreLabel}
              </Typography.Text>
            )}
          </div>
        )}
      </div>
      <ul className="m-0 min-w-[150px] list-none p-0" aria-label="Breakdown">
        {slices.map((s) => {
          const pctValue = total ? Math.round((s.value / total) * 100) : 0;
          const row = (
            <>
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ background: s.color }}
                aria-hidden
              />
              <span className="flex-1">{s.label}</span>
              <Typography.Text strong className="tabular-nums">
                {s.value}
              </Typography.Text>
              <Typography.Text type="secondary" className="w-10 text-right tabular-nums text-xs">
                {pctValue}%
              </Typography.Text>
            </>
          );
          return (
            <li key={s.key} className="py-1">
              {onSelect ? (
                <button
                  type="button"
                  onClick={() => onSelect(s.key)}
                  className="flex w-full items-center gap-2 rounded px-1 text-left hover:bg-[rgba(29,78,216,0.08)]"
                  aria-label={`${s.label}: ${s.value}, ${pctValue} percent. Show these`}
                >
                  {row}
                </button>
              ) : (
                <div className="flex items-center gap-2 px-1">{row}</div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
