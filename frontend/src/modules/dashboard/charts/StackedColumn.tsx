import { Column } from "@ant-design/plots";
import { useChartTheme } from "./theme";

export interface StackSeries {
  key: string;
  label: string;
  color: string;
  points: { x: string; y: number }[];
}

/** Stacked columns per period — the right shape for "how much, and of
 * what kind" questions such as deployment outcomes per day. */
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
  const data = series.flatMap((s) => s.points.map((p) => ({ x: p.x, type: s.label, value: p.y })));

  return (
    <div style={{ height }} role="img" aria-label={`${series.map((s) => s.label).join(", ")} per period`}>
      <Column
        data={data}
        xField="x"
        yField="value"
        colorField="type"
        height={height}
        autoFit
        animate={false}
        theme={chart.g2}
        viewStyle={chart.viewStyle}
        transform={[{ type: "stackY" }]}
        scale={{ color: { range: series.map((s) => s.color) }, y: { nice: true } }}
        axis={{
          x: { title: false, labelAutoHide: true, labelFormatter: xLabel, line: false, tick: false },
          y: { title: false, gridLineDash: [3, 3], gridStroke: chart.grid, line: false, tick: false },
        }}
        legend={{ color: { position: "top", itemMarker: "square" } }}
        style={{ radiusTopLeft: 3, radiusTopRight: 3, maxWidth: 28 }}
        tooltip={{ title: (d: { x: string }) => (xLabel ? xLabel(d.x) : d.x) }}
      />
    </div>
  );
}
