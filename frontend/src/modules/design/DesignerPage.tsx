import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Asset } from "../content/types";
import {
  newZoneKey,
  ZONE_CONTENT_TYPES,
  type DataVariable,
  type LayoutCanvas,
  type LayoutDetail,
  type Widget,
  type ZoneDef,
} from "./types";

const CANVAS_DISPLAY_WIDTH = 820;

type DragState =
  | { kind: "move"; key: string; startX: number; startY: number; origX: number; origY: number }
  | {
      kind: "resize";
      key: string;
      startX: number;
      startY: number;
      origW: number;
      origH: number;
    };

/** SCR-16 Screen Designer: canvas, zones, drag/resize, properties, publish. */
export function DesignerPage() {
  const { layoutId } = useParams<{ layoutId: string }>();
  const { hasPermission } = useAuth();
  const canManage = hasPermission("layouts.manage");
  const queryClient = useQueryClient();

  const [canvas, setCanvas] = useState<LayoutCanvas | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const dragRef = useRef<DragState | null>(null);

  const layoutQuery = useQuery({
    queryKey: ["layout", layoutId],
    queryFn: () => api.get<LayoutDetail>(`/layouts/${layoutId}`),
  });
  const assetsQuery = useQuery({
    queryKey: ["assets-for-designer"],
    queryFn: () => api.get<Asset[]>("/assets?page_size=100"),
  });

  const layout = layoutQuery.data?.data ?? null;
  useEffect(() => {
    if (layout && canvas === null) {
      setCanvas(layout.draft_canvas_json);
    }
  }, [layout, canvas]);

  const scale = canvas ? CANVAS_DISPLAY_WIDTH / canvas.canvas.width : 1;

  const updateZone = useCallback((key: string, patch: Partial<ZoneDef>) => {
    setCanvas((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        zones: prev.zones.map((z) => (z.key === key ? { ...z, ...patch } : z)),
      };
    });
    setDirty(true);
  }, []);

  // Global mouse handlers for drag/resize sessions.
  useEffect(() => {
    function onMove(e: MouseEvent) {
      const drag = dragRef.current;
      if (!drag || !canvas) return;
      const dx = (e.clientX - drag.startX) / scale;
      const dy = (e.clientY - drag.startY) / scale;
      if (drag.kind === "move") {
        updateZone(drag.key, {
          x: Math.max(0, Math.round(drag.origX + dx)),
          y: Math.max(0, Math.round(drag.origY + dy)),
        });
      } else {
        updateZone(drag.key, {
          width: Math.max(20, Math.round(drag.origW + dx)),
          height: Math.max(20, Math.round(drag.origH + dy)),
        });
      }
    }
    function onUp() {
      dragRef.current = null;
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [canvas, scale, updateZone]);

  const save = useMutation({
    mutationFn: () => api.patch(`/layouts/${layoutId}`, { canvas_json: canvas }),
    onSuccess: () => {
      setDirty(false);
      setMessage({ kind: "ok", text: "Draft saved." });
      queryClient.invalidateQueries({ queryKey: ["layout", layoutId] });
      queryClient.invalidateQueries({ queryKey: ["layouts"] });
    },
    onError: (err) =>
      setMessage({
        kind: "error",
        text: err instanceof ApiError ? err.message : "Failed to save draft",
      }),
  });

  const publish = useMutation({
    mutationFn: async () => {
      if (dirty) await api.patch(`/layouts/${layoutId}`, { canvas_json: canvas });
      return api.post(`/layouts/${layoutId}/publish`);
    },
    onSuccess: () => {
      setDirty(false);
      setMessage({ kind: "ok", text: "Layout published." });
      queryClient.invalidateQueries({ queryKey: ["layout", layoutId] });
      queryClient.invalidateQueries({ queryKey: ["layouts"] });
    },
    onError: (err) =>
      setMessage({
        kind: "error",
        text: err instanceof ApiError ? err.message : "Failed to publish",
      }),
  });

  const saveAsTemplate = useMutation({
    mutationFn: (name: string) => api.post("/templates", { layout_id: layoutId, name }),
    onSuccess: () => {
      setMessage({ kind: "ok", text: "Saved as a draft template (Design → Templates)." });
      queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (err) =>
      setMessage({
        kind: "error",
        text: err instanceof ApiError ? err.message : "Failed to save template",
      }),
  });

  if (layoutQuery.isLoading || !canvas || !layout) {
    return <Spinner label="Loading designer…" />;
  }

  const selected = canvas.zones.find((z) => z.key === selectedKey) ?? null;
  const assets = (assetsQuery.data?.data ?? []).filter(
    (a) => a.current_version?.processing_status === "ready",
  );
  const assetById = new Map(assets.map((a) => [a.id, a]));

  function addZone() {
    if (!canvas) return;
    const key = newZoneKey(canvas.zones.map((z) => z.key));
    const zone: ZoneDef = {
      key,
      name: `Zone ${canvas.zones.length + 1}`,
      x: 40,
      y: 40,
      width: Math.round(canvas.canvas.width / 3),
      height: Math.round(canvas.canvas.height / 3),
      z_index: canvas.zones.length + 1,
      rotation: 0,
      style: {},
      content_type: "placeholder",
      content_config: {},
    };
    setCanvas({ ...canvas, zones: [...canvas.zones, zone] });
    setSelectedKey(key);
    setDirty(true);
  }

  function deleteZone(key: string) {
    if (!canvas) return;
    setCanvas({ ...canvas, zones: canvas.zones.filter((z) => z.key !== key) });
    if (selectedKey === key) setSelectedKey(null);
    setDirty(true);
  }

  function duplicateZone(zone: ZoneDef) {
    if (!canvas) return;
    const key = newZoneKey(canvas.zones.map((z) => z.key));
    setCanvas({
      ...canvas,
      zones: [
        ...canvas.zones,
        { ...zone, key, name: `${zone.name} copy`, x: zone.x + 40, y: zone.y + 40 },
      ],
    });
    setSelectedKey(key);
    setDirty(true);
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/design" className="text-sm text-slate-500 hover:underline">
            ← Layouts
          </Link>
          <h1 className="text-xl font-semibold text-slate-900">
            {layout.name}
            <span className="ml-3 align-middle">
              <StatusBadge status={layout.status} />
            </span>
            {dirty && <span className="ml-2 text-sm font-normal text-amber-600">● unsaved</span>}
          </h1>
        </div>
        {canManage && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={addZone}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
            >
              Add zone
            </button>
            <button
              type="button"
              onClick={() => save.mutate()}
              disabled={save.isPending || !dirty}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 disabled:opacity-40"
            >
              {save.isPending ? "Saving…" : "Save draft"}
            </button>
            <button
              type="button"
              onClick={() => {
                const name = window.prompt("Template name:", `${layout.name} template`);
                if (name) saveAsTemplate.mutate(name);
              }}
              disabled={saveAsTemplate.isPending}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 disabled:opacity-40"
            >
              Save as template
            </button>
            <button
              type="button"
              onClick={() => publish.mutate()}
              disabled={publish.isPending}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {publish.isPending ? "Publishing…" : "Publish"}
            </button>
          </div>
        )}
      </div>

      {message && (
        <p
          role="alert"
          className={`mt-2 rounded-md px-3 py-2 text-sm ${
            message.kind === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </p>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="overflow-auto rounded-lg border border-slate-200 bg-slate-100 p-4">
          <div
            className="relative mx-auto overflow-hidden shadow"
            style={{
              width: canvas.canvas.width * scale,
              height: canvas.canvas.height * scale,
              background: canvas.canvas.background ?? "#000",
            }}
            onMouseDown={() => setSelectedKey(null)}
            role="application"
            aria-label="Layout canvas"
          >
            {[...canvas.zones]
              .sort((a, b) => a.z_index - b.z_index)
              .map((zone) => {
                const asset = zone.content_config.asset_id
                  ? assetById.get(String(zone.content_config.asset_id))
                  : null;
                const isSelected = zone.key === selectedKey;
                return (
                  <div
                    key={zone.key}
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      setSelectedKey(zone.key);
                      if (canManage) {
                        dragRef.current = {
                          kind: "move",
                          key: zone.key,
                          startX: e.clientX,
                          startY: e.clientY,
                          origX: zone.x,
                          origY: zone.y,
                        };
                      }
                    }}
                    className={`absolute flex items-center justify-center overflow-hidden text-xs ${
                      isSelected ? "ring-2 ring-sky-400" : "ring-1 ring-white/30"
                    }`}
                    style={{
                      left: zone.x * scale,
                      top: zone.y * scale,
                      width: zone.width * scale,
                      height: zone.height * scale,
                      zIndex: zone.z_index,
                      background:
                        (zone.style.background as string) ??
                        (zone.content_type === "placeholder" ? "#1e293b" : "#0f172a"),
                      cursor: canManage ? "move" : "default",
                    }}
                  >
                    {asset?.thumbnail_url ? (
                      <img
                        src={asset.thumbnail_url}
                        alt=""
                        className="h-full w-full object-cover opacity-90"
                        draggable={false}
                      />
                    ) : zone.content_type === "text" || zone.content_type === "ticker" ? (
                      <span className="px-2 text-white/90">
                        {String(zone.content_config.text ?? zone.name)}
                      </span>
                    ) : (
                      <span className="text-white/60">
                        {zone.name} · {zone.content_type}
                      </span>
                    )}
                    {canManage && isSelected && (
                      <span
                        onMouseDown={(e) => {
                          e.stopPropagation();
                          dragRef.current = {
                            kind: "resize",
                            key: zone.key,
                            startX: e.clientX,
                            startY: e.clientY,
                            origW: zone.width,
                            origH: zone.height,
                          };
                        }}
                        aria-label="Resize zone"
                        className="absolute bottom-0 right-0 h-3 w-3 cursor-nwse-resize bg-sky-400"
                      />
                    )}
                  </div>
                );
              })}
          </div>
          <p className="mt-2 text-center text-xs text-slate-400">
            {canvas.canvas.width}×{canvas.canvas.height} · scale {(scale * 100).toFixed(0)}%
          </p>
        </div>

        <aside className="rounded-lg border border-slate-200 bg-white p-4">
          {!selected ? (
            <p className="text-sm text-slate-500">
              Select a zone on the canvas to edit its properties.
            </p>
          ) : (
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-slate-800">{selected.name}</h2>
                {canManage && (
                  <div className="space-x-2 text-xs">
                    <button
                      type="button"
                      onClick={() => duplicateZone(selected)}
                      className="font-medium text-slate-500 hover:underline"
                    >
                      Duplicate
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteZone(selected.key)}
                      className="font-medium text-red-600 hover:underline"
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
              <PropInput
                label="Name"
                value={selected.name}
                onChange={(v) => updateZone(selected.key, { name: v })}
                disabled={!canManage}
              />
              <div className="grid grid-cols-2 gap-2">
                {(["x", "y", "width", "height"] as const).map((prop) => (
                  <PropInput
                    key={prop}
                    label={prop}
                    type="number"
                    value={String(Math.round(selected[prop]))}
                    onChange={(v) =>
                      updateZone(selected.key, { [prop]: Math.max(0, Number(v) || 0) })
                    }
                    disabled={!canManage}
                  />
                ))}
              </div>
              <PropInput
                label="Z-index"
                type="number"
                value={String(selected.z_index)}
                onChange={(v) => updateZone(selected.key, { z_index: Number(v) || 0 })}
                disabled={!canManage}
              />
              <PropInput
                label="Background (CSS color)"
                value={String(selected.style.background ?? "")}
                onChange={(v) =>
                  updateZone(selected.key, { style: { ...selected.style, background: v || null } })
                }
                disabled={!canManage}
              />
              <div>
                <label htmlFor="zone-content-type" className="block text-xs font-medium uppercase tracking-wide text-slate-400">
                  Content type
                </label>
                <select
                  id="zone-content-type"
                  value={selected.content_type}
                  disabled={!canManage}
                  onChange={(e) =>
                    updateZone(selected.key, { content_type: e.target.value, content_config: {} })
                  }
                  className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5"
                >
                  {ZONE_CONTENT_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              {(selected.content_type === "image" || selected.content_type === "video") && (
                <div>
                  <label htmlFor="zone-asset" className="block text-xs font-medium uppercase tracking-wide text-slate-400">
                    Asset
                  </label>
                  <select
                    id="zone-asset"
                    value={String(selected.content_config.asset_id ?? "")}
                    disabled={!canManage}
                    onChange={(e) =>
                      updateZone(selected.key, {
                        content_config: e.target.value ? { asset_id: e.target.value } : {},
                      })
                    }
                    className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5"
                  >
                    <option value="">— choose —</option>
                    {assets
                      .filter((a) => a.type === selected.content_type)
                      .map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.name}
                        </option>
                      ))}
                  </select>
                </div>
              )}
              {(selected.content_type === "text" || selected.content_type === "ticker") && (
                <PropInput
                  label="Text"
                  value={String(selected.content_config.text ?? "")}
                  onChange={(v) =>
                    updateZone(selected.key, {
                      content_config: { ...selected.content_config, text: v },
                    })
                  }
                  disabled={!canManage}
                />
              )}
              {selected.content_type === "web" && (
                <PropInput
                  label="URL"
                  value={String(selected.content_config.url ?? "")}
                  onChange={(v) =>
                    updateZone(selected.key, {
                      content_config: { ...selected.content_config, url: v },
                    })
                  }
                  disabled={!canManage}
                />
              )}
              {selected.content_type === "widget" && (
                <WidgetZonePanel
                  zone={selected}
                  updateZone={updateZone}
                  disabled={!canManage}
                />
              )}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

/** P2-07 binding panel: widget instance + schema-driven config + data
 * variables ({{token}}) for dynamic text. */
function WidgetZonePanel({
  zone,
  updateZone,
  disabled,
}: {
  zone: ZoneDef;
  updateZone: (key: string, patch: Partial<ZoneDef>) => void;
  disabled: boolean;
}) {
  const widgetsQuery = useQuery({
    queryKey: ["widgets"],
    queryFn: () => api.get<Widget[]>("/widgets"),
  });
  const variablesQuery = useQuery({
    queryKey: ["data-variables"],
    queryFn: () => api.get<DataVariable[]>("/data-variables"),
  });

  const widgets = (widgetsQuery.data?.data ?? []).filter((w) => w.status === "active");
  const ref = zone.widget ?? null;
  const widget = widgets.find((w) => w.id === ref?.widget_id) ?? null;
  const schema = widget?.versions[widget.versions.length - 1]?.config_schema_json;

  function patchWidget(patch: Partial<NonNullable<ZoneDef["widget"]>>) {
    updateZone(zone.key, {
      widget: ref
        ? { ...ref, ...patch }
        : { widget_id: "", config: {}, bindings: {}, ...patch },
    });
  }

  return (
    <div className="space-y-3 border-t border-slate-200 pt-3">
      <div>
        <label htmlFor="zone-widget" className="block text-xs font-medium uppercase tracking-wide text-slate-400">
          Widget
        </label>
        <select
          id="zone-widget"
          value={ref?.widget_id ?? ""}
          disabled={disabled}
          onChange={(e) =>
            updateZone(zone.key, {
              widget: e.target.value
                ? { widget_id: e.target.value, config: {}, bindings: {} }
                : null,
            })
          }
          className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5"
        >
          <option value="">— choose widget —</option>
          {widgets.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name} ({w.type})
            </option>
          ))}
        </select>
      </div>

      {schema &&
        ref &&
        schema.fields.map((field) => {
          const value = ref.config?.[field.key];
          const set = (v: unknown) =>
            patchWidget({ config: { ...ref.config, [field.key]: v } });
          if (field.type === "boolean") {
            return (
              <label key={field.key} className="flex items-center gap-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={Boolean(value)}
                  disabled={disabled}
                  onChange={(e) => set(e.target.checked)}
                />
                {field.label ?? field.key}
                {field.required && <span className="text-red-500">*</span>}
              </label>
            );
          }
          if (field.type === "select") {
            return (
              <div key={field.key}>
                <label className="block text-xs font-medium uppercase tracking-wide text-slate-400">
                  {field.label ?? field.key}
                  {field.required && <span className="text-red-500">*</span>}
                </label>
                <select
                  value={String(value ?? field.default ?? "")}
                  disabled={disabled}
                  onChange={(e) => set(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5"
                >
                  <option value="">— choose —</option>
                  {(field.options ?? []).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </div>
            );
          }
          return (
            <PropInput
              key={field.key}
              label={`${field.label ?? field.key}${field.required ? " *" : ""}`}
              type={field.type === "number" ? "number" : field.type === "color" ? "color" : "text"}
              value={String(value ?? field.default ?? "")}
              onChange={(v) => set(field.type === "number" ? Number(v) : v)}
              disabled={disabled}
            />
          );
        })}

      {ref && (
        <div>
          <PropInput
            label="Text binding"
            value={ref.bindings?.text ?? ""}
            onChange={(v) => patchWidget({ bindings: { ...ref.bindings, text: v } })}
            disabled={disabled}
          />
          <p className="mt-1 text-xs text-slate-400">
            Use {"{{token}}"} with approved variables:{" "}
            {(variablesQuery.data?.data ?? []).map((v) => v.token).join(", ")}
          </p>
        </div>
      )}
      {ref && <DataBindingEditor refWidget={ref} patchWidget={patchWidget} disabled={disabled} />}
      {widget?.fallback_json && (
        <p className="text-xs text-slate-400">
          Fallback when data unavailable: {JSON.stringify(widget.fallback_json)}
        </p>
      )}
    </div>
  );
}

/** P3-04 (3A-2): bind the widget to a live data source with a safe
 * declarative transform. The player receives validated snapshots via the
 * manifest `data` block — never a raw feed. */
function DataBindingEditor({
  refWidget,
  patchWidget,
  disabled,
}: {
  refWidget: NonNullable<ZoneDef["widget"]>;
  patchWidget: (patch: Partial<NonNullable<ZoneDef["widget"]>>) => void;
  disabled: boolean;
}) {
  const sourcesQuery = useQuery({
    queryKey: ["data-sources"],
    queryFn: () => api.get<{ id: string; name: string; state: string }[]>("/data-sources"),
  });
  const sources = sourcesQuery.data?.data ?? [];
  const binding = refWidget.data_binding ?? null;
  const transform = binding?.transform ?? {};

  function patchBinding(patch: Record<string, unknown>) {
    patchWidget({
      data_binding: { source_id: binding?.source_id ?? "", ...binding, ...patch },
    });
  }

  return (
    <div className="border-t border-slate-200 pt-3">
      <label htmlFor="zone-data-source" className="block text-xs font-medium uppercase tracking-wide text-slate-400">
        Live data source
      </label>
      <select
        id="zone-data-source"
        value={binding?.source_id ?? ""}
        disabled={disabled}
        onChange={(e) =>
          patchWidget({
            data_binding: e.target.value ? { source_id: e.target.value } : null,
          })
        }
        className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5"
      >
        <option value="">— no live data —</option>
        {sources.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name} {s.state !== "active" ? `(${s.state})` : ""}
          </option>
        ))}
      </select>
      {binding && (
        <div className="mt-2 space-y-2">
          <PropInput
            label="Transform path (e.g. items)"
            value={String(transform.path ?? "")}
            onChange={(v) => patchBinding({ transform: { ...transform, path: v || undefined } })}
            disabled={disabled}
          />
          <PropInput
            label="Fields (out:in, comma-separated)"
            value={Object.entries(transform.fields ?? {})
              .map(([k, v]) => `${k}:${v}`)
              .join(", ")}
            onChange={(v) => {
              const fields: Record<string, string> = {};
              for (const pair of v.split(",")) {
                const [out, inPath] = pair.split(":").map((s) => s.trim());
                if (out && inPath) fields[out] = inPath;
              }
              patchBinding({
                transform: {
                  ...transform,
                  fields: Object.keys(fields).length ? fields : undefined,
                },
              });
            }}
            disabled={disabled}
          />
          <PropInput
            label="Item limit"
            type="number"
            value={String(transform.limit ?? "")}
            onChange={(v) =>
              patchBinding({
                transform: { ...transform, limit: v ? Number(v) : undefined },
              })
            }
            disabled={disabled}
          />
          <p className="text-xs text-slate-400">
            Snapshots are refreshed server-side; when the source is down the
            player keeps last-known-good, then the widget fallback.
          </p>
        </div>
      )}
    </div>
  );
}

function PropInput({
  label,
  value,
  onChange,
  type = "text",
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  disabled?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </label>
      <input
        type={type}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 disabled:bg-slate-50"
      />
    </div>
  );
}
