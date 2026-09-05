import { EnvironmentOutlined } from "@ant-design/icons";
import { Button, Descriptions, Select, Space, Tag, Typography, theme } from "antd";
import type { LatLngBoundsExpression } from "leaflet";
import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import { Link } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import { toneStyle } from "@/design-system";
import { useThemeMode } from "@/design-system";
import { ChartFrame } from "@/design-system";
import { STATUS_COLORS } from "../charts/theme";
import type { GeoAnchor } from "../types";
import { ViewAll } from "./shared";

interface CityGroup {
  key: string;
  name: string;
  state: string | null;
  latitude: number;
  longitude: number;
  devices: number;
  online: number;
  warning: number;
  offline: number;
  campaigns: number;
  anchors: GeoAnchor[];
}

type HealthFilter = "all" | "issues" | "healthy";

function healthOf(g: { devices: number; online: number; offline: number }) {
  if (!g.devices) return { key: "na", color: STATUS_COLORS.na, label: "No active devices" };
  const share = g.online / g.devices;
  if (g.offline === 0 && share >= 0.9) return { key: "healthy", color: STATUS_COLORS.online, label: "Healthy" };
  if (share >= 0.7) return { key: "warning", color: STATUS_COLORS.warning, label: "Degraded" };
  return { key: "offline", color: STATUS_COLORS.offline, label: "Critical" };
}

function groupByCity(anchors: GeoAnchor[]): CityGroup[] {
  const groups = new Map<string, CityGroup>();
  for (const a of anchors) {
    const name = a.city ?? a.name;
    const key = `${a.state ?? ""}/${name}`;
    const g = groups.get(key) ?? {
      key,
      name,
      state: a.state,
      latitude: 0,
      longitude: 0,
      devices: 0,
      online: 0,
      warning: 0,
      offline: 0,
      campaigns: 0,
      anchors: [],
    };
    g.devices += a.devices;
    g.online += a.online;
    g.warning += a.warning;
    g.offline += a.offline;
    g.campaigns = Math.max(g.campaigns, a.campaigns);
    g.anchors.push(a);
    groups.set(key, g);
  }
  for (const g of groups.values()) {
    // Prefer the city node's own coordinates; otherwise centre on members.
    const cityNode = g.anchors.find((a) => a.type === "city");
    if (cityNode) {
      g.latitude = cityNode.latitude;
      g.longitude = cityNode.longitude;
    } else {
      g.latitude = g.anchors.reduce((s, a) => s + a.latitude, 0) / g.anchors.length;
      g.longitude = g.anchors.reduce((s, a) => s + a.longitude, 0) / g.anchors.length;
    }
  }
  return [...groups.values()].sort((a, b) => b.devices - a.devices);
}

function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 11);
      return;
    }
    map.fitBounds(points as LatLngBoundsExpression, { padding: [24, 24], maxZoom: 12 });
  }, [map, points]);
  return null;
}

/** The signage footprint on a real map. Markers are actual location
 * records rolled up by city; click a city to see its stores and zones.
 * The list beside the map is the same data in text, and takes over
 * entirely if tiles cannot load. */
export function LocationMapWidget({
  anchors,
  loading,
  error,
  onRetry,
}: {
  anchors?: GeoAnchor[];
  loading: boolean;
  error?: unknown;
  onRetry: () => void;
}) {
  const { mode } = useThemeMode();
  const { token } = theme.useToken();
  const [stateFilter, setStateFilter] = useState<string | null>(null);
  const [healthFilter, setHealthFilter] = useState<HealthFilter>("all");
  const [focus, setFocus] = useState<CityGroup | null>(null);
  const [tilesFailed, setTilesFailed] = useState(false);

  const cities = useMemo(() => groupByCity(anchors ?? []), [anchors]);
  const states = useMemo(
    () => [...new Set(cities.map((c) => c.state).filter((s): s is string => !!s))].sort(),
    [cities],
  );
  const visible = cities.filter((c) => {
    if (stateFilter && c.state !== stateFilter) return false;
    const h = healthOf(c).key;
    if (healthFilter === "issues") return h === "warning" || h === "offline";
    if (healthFilter === "healthy") return h === "healthy";
    return true;
  });

  const markers: { key: string; name: string; sub: string | null; lat: number; lng: number; devices: number; online: number; warning: number; offline: number; campaigns: number }[] =
    focus
      ? focus.anchors.map((a) => ({
          key: a.location_id,
          name: a.name,
          sub: a.type,
          lat: a.latitude,
          lng: a.longitude,
          devices: a.devices,
          online: a.online,
          warning: a.warning,
          offline: a.offline,
          campaigns: a.campaigns,
        }))
      : visible.map((c) => ({
          key: c.key,
          name: c.name,
          sub: c.state,
          lat: c.latitude,
          lng: c.longitude,
          devices: c.devices,
          online: c.online,
          warning: c.warning,
          offline: c.offline,
          campaigns: c.campaigns,
        }));
  const points = useMemo(() => markers.map((m) => [m.lat, m.lng] as [number, number]), [markers]);

  const totalDevices = visible.reduce((n, c) => n + c.devices, 0);
  const summary = anchors
    ? `${cities.length} cities across ${states.length} states, ${totalDevices} active displays placed on the map.`
    : undefined;

  return (
    <ChartFrame
      title={focus ? `Signage network — ${focus.name}` : "Signage network — India"}
      extra={<ViewAll to="/locations" label="Locations" />}
      summary={summary}
      loading={loading && !anchors}
      error={error}
      onRetry={onRetry}
      empty={!!anchors && anchors.length === 0}
      emptyTitle="No locations with coordinates"
      emptyDescription="Add latitude and longitude to your stores or cities and the map fills in."
    >
      <Space wrap size="small" className="mb-3">
        {focus ? (
          <Button size="small" onClick={() => setFocus(null)}>
            ← All of India
          </Button>
        ) : (
          <>
            <Select
              size="small"
              allowClear
              placeholder="All states"
              value={stateFilter}
              onChange={(v) => setStateFilter(v ?? null)}
              options={states.map((s) => ({ value: s, label: s }))}
              className="w-40"
              aria-label="Filter by state"
            />
            <Select
              size="small"
              value={healthFilter}
              onChange={(v) => setHealthFilter(v)}
              options={[
                { value: "all", label: "All cities" },
                { value: "issues", label: "With issues" },
                { value: "healthy", label: "Healthy" },
              ]}
              className="w-32"
              aria-label="Filter by health"
            />
          </>
        )}
      </Space>

      <div className="grid gap-4 lg:grid-cols-[1.618fr_1fr]">
        {!tilesFailed && (
          <div className="overflow-hidden rounded-lg" style={{ height: 340 }} aria-hidden>
            <MapContainer
              center={[22.5, 79]}
              zoom={4}
              scrollWheelZoom={false}
              style={{ height: "100%", width: "100%" }}
              attributionControl
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                className={mode === "dark" ? "[filter:invert(1)_hue-rotate(180deg)_brightness(0.9)_contrast(0.9)]" : undefined}
                eventHandlers={{ tileerror: () => setTilesFailed(true) }}
              />
              <FitBounds points={points} />
              {markers.map((m) => {
                const h = healthOf(m);
                return (
                  <CircleMarker
                    key={m.key}
                    center={[m.lat, m.lng]}
                    radius={Math.max(7, Math.min(22, 5 + Math.sqrt(m.devices) * 3))}
                    pathOptions={{ color: h.color, fillColor: h.color, fillOpacity: 0.55, weight: 2 }}
                    eventHandlers={{
                      click: () => {
                        if (!focus) {
                          const city = visible.find((c) => c.key === m.key);
                          if (city && city.anchors.length > 1) setFocus(city);
                        }
                      },
                    }}
                  >
                    <Popup>
                      <div style={{ minWidth: 180 }}>
                        <strong>{m.name}</strong>
                        {m.sub && <div style={{ opacity: 0.7, fontSize: 12 }}>{m.sub}</div>}
                        <div style={{ marginTop: 6 }}>
                          <Tag color={h.key === "healthy" ? "success" : h.key === "warning" ? "warning" : h.key === "offline" ? "error" : "default"}>
                            {h.label}
                          </Tag>
                        </div>
                        <Descriptions
                          size="small"
                          column={1}
                          colon={false}
                          style={{ marginTop: 6 }}
                          styles={{ label: { fontSize: 12 }, content: { fontSize: 12, textAlign: "right" } }}
                          items={[
                            { key: "devices", label: "Devices", children: m.devices },
                            { key: "online", label: "Online", children: m.online },
                            { key: "warning", label: "Warning", children: m.warning },
                            { key: "offline", label: "Offline", children: m.offline },
                            { key: "campaigns", label: "Campaigns", children: m.campaigns },
                          ]}
                        />
                        <div style={{ marginTop: 6 }}>
                          <Link to={focus ? `/locations?id=${m.key}` : "/locations"}>View location</Link>
                        </div>
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}
            </MapContainer>
          </div>
        )}

        <div className="min-w-0">
          {tilesFailed && (
            <Typography.Paragraph type="secondary" className="text-xs">
              Map tiles could not be loaded (no internet access?). The footprint is listed below.
            </Typography.Paragraph>
          )}
          <ul style={{ margin: 0, maxHeight: 340, listStyle: "none", overflow: "auto", padding: 0 }} aria-label="Locations by city">
            {markers.map((m) => {
              const h = healthOf(m);
              return (
                <li key={m.key} style={{ borderBottom: `1px solid ${token.colorBorderSecondary}` }}>
                  <Button
                    type="text"
                    block
                    style={{ height: "auto", paddingBlock: 8, paddingInline: 4, justifyContent: "flex-start", textAlign: "left" }}
                    onClick={() => {
                      if (!focus) {
                        const city = visible.find((c) => c.key === m.key);
                        if (city && city.anchors.length > 1) setFocus(city);
                      }
                    }}
                    aria-label={`${m.name}: ${m.devices} devices, ${m.online} online, ${m.offline} offline. ${h.label}`}
                  >
                    <EnvironmentOutlined style={{ color: h.color }} aria-hidden />
                    <span style={{ minWidth: 0, flex: 1, display: "block" }}>
                      <Typography.Text strong className="block truncate">
                        {m.name}
                      </Typography.Text>
                      <Typography.Text type="secondary" className="block truncate text-xs">
                        {m.sub ?? ""}
                        {m.sub ? " · " : ""}
                        {m.devices} devices · {m.online} online · {m.offline} offline
                      </Typography.Text>
                    </span>
                    <Tag style={{ ...toneStyle(h.key === "healthy" ? "success" : h.key === "warning" ? "warning" : h.key === "offline" ? "error" : "default", mode), marginInlineEnd: 0 }}
                    >
                      {h.label}
                    </Tag>
                  </Button>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </ChartFrame>
  );
}
