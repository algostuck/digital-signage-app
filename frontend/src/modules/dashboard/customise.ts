import { useCallback, useEffect, useState } from "react";

/** Widgets the administrator can hide or reorder. Keys are stable — they
 * are what gets persisted. Order here is the default order. */
export const WIDGETS = [
  { key: "kpis", label: "KPI summary", tier: 1 },
  { key: "device_health", label: "Device health", tier: 1 },
  { key: "attention", label: "Needs attention", tier: 1 },
  { key: "map", label: "Signage network map", tier: 1 },
  { key: "campaigns", label: "Campaign performance", tier: 1 },
  { key: "playback", label: "Playback / proof of play", tier: 2 },
  { key: "deployments", label: "Deployments", tier: 2 },
  { key: "content", label: "Content", tier: 2 },
  { key: "locations_top", label: "Top locations", tier: 2 },
  { key: "now_playing", label: "Now playing", tier: 2 },
  { key: "live_screens", label: "Live screens", tier: 2 },
  { key: "activity", label: "Recent activity", tier: 2 },
  { key: "approvals", label: "Pending approvals", tier: 3 },
  { key: "schedule", label: "Today's schedule", tier: 3 },
  { key: "usage", label: "Subscription & usage", tier: 3 },
  { key: "insights", label: "Insights", tier: 3 },
] as const;

export type WidgetKey = (typeof WIDGETS)[number]["key"];

interface Layout {
  hidden: WidgetKey[];
  order: WidgetKey[];
}

const DEFAULT_LAYOUT: Layout = { hidden: [], order: WIDGETS.map((w) => w.key) };

function storageKey(userId: string) {
  return `dsc.dashboard.layout.${userId}`;
}

function load(userId: string): Layout {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return DEFAULT_LAYOUT;
    const parsed = JSON.parse(raw) as Partial<Layout>;
    const known = new Set<string>(WIDGETS.map((w) => w.key));
    const order = (parsed.order ?? []).filter((k): k is WidgetKey => known.has(k));
    // Widgets added after the layout was saved appear at the end, visible.
    for (const w of WIDGETS) if (!order.includes(w.key)) order.push(w.key);
    return {
      hidden: (parsed.hidden ?? []).filter((k): k is WidgetKey => known.has(k)),
      order,
    };
  } catch {
    return DEFAULT_LAYOUT;
  }
}

/** Per-browser, per-user dashboard layout. Deliberately not server-side:
 * the brief allows customisation only where it fits cleanly, and a new
 * preference table for a hide/show list would not. */
export function useDashboardLayout(userId: string | undefined) {
  const [layout, setLayout] = useState<Layout>(DEFAULT_LAYOUT);
  useEffect(() => {
    if (userId) setLayout(load(userId));
  }, [userId]);

  const persist = useCallback(
    (next: Layout) => {
      setLayout(next);
      if (!userId) return;
      try {
        localStorage.setItem(storageKey(userId), JSON.stringify(next));
      } catch {
        // Storage unavailable: the layout still applies for this session.
      }
    },
    [userId],
  );

  return {
    order: layout.order,
    isVisible: (key: WidgetKey) => !layout.hidden.includes(key),
    toggle: (key: WidgetKey) =>
      persist({
        ...layout,
        hidden: layout.hidden.includes(key)
          ? layout.hidden.filter((k) => k !== key)
          : [...layout.hidden, key],
      }),
    move: (key: WidgetKey, direction: -1 | 1) => {
      const index = layout.order.indexOf(key);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= layout.order.length) return;
      const order = [...layout.order];
      [order[index], order[target]] = [order[target], order[index]];
      persist({ ...layout, order });
    },
    reset: () => persist(DEFAULT_LAYOUT),
    isDefault: layout.hidden.length === 0 && layout.order.join() === DEFAULT_LAYOUT.order.join(),
  };
}
