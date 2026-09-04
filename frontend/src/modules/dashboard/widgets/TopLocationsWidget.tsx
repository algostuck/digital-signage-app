import { useNavigate } from "react-router-dom";
import { ChartFrame } from "../charts/ChartFrame";
import { RankBar } from "../charts/RankBar";
import { STATUS_COLORS } from "../charts/theme";
import type { TopLocation } from "../types";
import { ViewAll } from "./shared";

/** Ranked by device health — the one location metric the platform can
 * stand behind today. Playback per location arrives with proof-of-play
 * by location; revenue and engagement do not exist and are not shown. */
export function TopLocationsWidget({
  locations,
  loading,
  error,
  onRetry,
}: {
  locations?: TopLocation[];
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  const navigate = useNavigate();
  return (
    <ChartFrame
      title="Top locations by device health"
      extra={<ViewAll to="/locations" />}
      summary={
        locations && locations.length
          ? `Best-performing sites by share of displays online; sites with fewer than two devices are not ranked.`
          : undefined
      }
      loading={loading && !locations}
      error={error}
      onRetry={onRetry}
      empty={!!locations && locations.length === 0}
      emptyTitle="Not enough data to rank"
      emptyDescription="Rankings appear once locations have two or more active displays."
    >
      {locations && (
        <RankBar
          ariaLabel="Top locations"
          max={100}
          rows={locations.map((l) => ({
            key: l.location_id,
            label: l.name,
            sublabel: `${l.city ? `${l.city} · ` : ""}${l.online}/${l.devices} online`,
            value: l.health_pct ?? 0,
            display: `${l.health_pct ?? 0}%`,
            color:
              (l.health_pct ?? 0) >= 90 ? STATUS_COLORS.online : (l.health_pct ?? 0) >= 70 ? STATUS_COLORS.warning : STATUS_COLORS.offline,
            onClick: () => navigate(`/locations?id=${l.location_id}`),
          }))}
        />
      )}
    </ChartFrame>
  );
}
