import { Column } from "@ant-design/plots";
import { useMemo } from "react";
import { useChartTheme } from "./theme";
import { ChartHost } from "./ChartHost";

export interface StackSeries {
  key: string;
  label: string;
  color: string;
  points: { x: string; y: number }[];
}

/** Stacked columns per period — the right shape for "how much, and of
 * what kind" questions such as deployment outcomes per day. Config is
 * memoised on the data for the same reason as TrendLine. */
export function StackedColumn({
  series,
  height = 200,
  xLabel,
}: {
  series: StackSeries[];
  height?: number;
  xLabel?: (x: string) => string;
}) {
  const chart = useChartTheme();
  const signature = JSON.stringify(series);
  const config = useMemo(() => {
    const data = series.flatMap((s) => s.points.map((p) => ({ x: p.x, type: s.label, value: p.y })));
    const format = xLabel ?? ((x: string) => x);
    return {
      data,
      xField: "x",
      yField: "value",
      colorField: "type",
      height,
      autoFit: true,
      animate: false,
      theme: chart.g2,
      viewStyle: chart.viewStyle,
      transform: [{ type: "stackY" }],
      scale: { color: { range: series.map((s) => s.color) }, y: { nice: true } },
      axis: {
        x: { title: false, labelAutoHide: true, labelFormatter: format, line: false, tick: false },
        y: { title: false, gridLineDash: [3, 3], gridStroke: chart.grid, line: false, tick: false },
      },
      legend: { color: { position: "top", itemMarker: "square" } },
      style: { radiusTopLeft: 3, radiusTopRight: 3, maxWidth: 28 },
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, height, chart.g2, chart.grid]);

  return (
    <div style={{ height }} role="img" aria-label={`${series.map((s) => s.label).join(", ")} per period`}>
      <ChartHost height={height}>
        <Column {...config} />
      </ChartHost>
    </div>
  );
}
