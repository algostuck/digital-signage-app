import { Line } from "@ant-design/plots";
import { useMemo } from "react";
import { useChartTheme } from "./theme";
import { ChartHost } from "./ChartHost";

export interface TrendSeries {
  key: string;
  label: string;
  color: string;
  points: { x: string; y: number }[];
}

/** Multi-series time line with an interactive legend (click to hide a
 * series) and a per-point tooltip listing every series.
 *
 * The whole G2 config is memoised on the data: the dashboard polls every
 * 30 s and re-renders its widgets, and a config whose formatter functions
 * change identity each render makes the plot tear itself down and rebuild
 * mid-render, which G2 does not survive. */
export function TrendLine({
  series,
  height = 220,
  xLabel,
  yLabel,
}: {
  series: TrendSeries[];
  height?: number;
  xLabel?: (x: string) => string;
  yLabel?: string;
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
      shapeField: "smooth",
      height,
      autoFit: true,
      animate: false,
      theme: chart.g2,
      viewStyle: chart.viewStyle,
      scale: { color: { range: series.map((s) => s.color) }, y: { nice: true } },
      axis: {
        x: { title: false, labelAutoHide: true, labelFormatter: format, line: false, tick: false },
        y: {
          title: yLabel ?? false,
          gridLineDash: [3, 3],
          gridStroke: chart.grid,
          line: false,
          tick: false,
        },
      },
      legend: { color: { position: "top", itemMarker: "circle" } },
      style: { lineWidth: 2 },
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, height, yLabel, chart.g2, chart.grid]);

  return (
    <div style={{ height }} role="img" aria-label={`${series.map((s) => s.label).join(", ")} over time`}>
      <ChartHost height={height}>
        <Line {...config} />
      </ChartHost>
    </div>
  );
}
