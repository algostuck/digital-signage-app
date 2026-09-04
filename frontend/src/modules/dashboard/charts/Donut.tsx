import { Pie } from "@ant-design/plots";
import { Typography } from "antd";
import { useChartTheme } from "./theme";

export interface DonutSlice {
  key: string;
  label: string;
  value: number;
  color: string;
}

/** Status-mix donut. Every slice carries a label and a value in the
 * legend list beside it, so the colours are reinforcement only. Clicking a
 * slice (or its legend row) drills into that status. */
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
  const data = slices.filter((s) => s.value > 0);
  const total = slices.reduce((n, s) => n + s.value, 0);

  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="relative min-w-[180px] flex-1" style={{ height }} aria-hidden>
        <Pie
          data={data}
          angleField="value"
          colorField="label"
          innerRadius={0.7}
          height={height}
          autoFit
          animate={false}
          legend={false}
          label={false}
          theme={chart.g2}
          viewStyle={chart.viewStyle}
          scale={{ color: { range: data.map((s) => s.color) } }}
          style={{ stroke: chart.surface, lineWidth: 2 }}
          tooltip={{
            title: (d: DonutSlice) => d.label,
            items: [
              {
                field: "value",
                name: "Devices",
                valueFormatter: (v: number) =>
                  `${v} · ${total ? Math.round((v / total) * 100) : 0}%`,
              },
            ],
          }}
          onEvent={(_chart, event) => {
            if (event.type === "element:click" && onSelect) {
              const label = (event.data?.data as DonutSlice | undefined)?.label;
              const slice = slices.find((s) => s.label === label);
              if (slice) onSelect(slice.key);
            }
          }}
        />
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
                  aria-label={`${s.label}: ${s.value}, ${pctValue} percent. Show these devices`}
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
