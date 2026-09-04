import { Line } from "@ant-design/plots";
import { useChartTheme } from "./theme";

export interface TrendSeries {
  key: string;
  label: string;
  color: string;
  points: { x: string; y: number }[];
}

/** Multi-series time line with an interactive legend (click to hide a
 * series) and a per-point tooltip listing every series. */
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
  const data = series.flatMap((s) => s.points.map((p) => ({ x: p.x, type: s.label, value: p.y })));
  const colors = series.map((s) => s.color);

  return (
    <div style={{ height }} role="img" aria-label={`${series.map((s) => s.label).join(", ")} over time`}>
      <Line
        data={data}
        xField="x"
        yField="value"
        colorField="type"
        shapeField="smooth"
        height={height}
        autoFit
        animate={false}
        theme={chart.g2}
        viewStyle={chart.viewStyle}
        scale={{ color: { range: colors }, y: { nice: true } }}
        axis={{
          x: {
            title: false,
            labelAutoHide: true,
            labelFormatter: xLabel,
            line: false,
            tick: false,
          },
          y: { title: yLabel ?? false, gridLineDash: [3, 3], gridStroke: chart.grid, line: false, tick: false },
        }}
        legend={{ color: { position: "top", itemMarker: "circle" } }}
        style={{ lineWidth: 2 }}
        tooltip={{ title: (d: { x: string }) => (xLabel ? xLabel(d.x) : d.x) }}
        interaction={{ tooltip: { marker: true, crosshairs: true } }}
      />
    </div>
  );
}
