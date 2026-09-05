
import { useQuery } from "@tanstack/react-query";
import { Checkbox, Select, Space, Typography } from "antd";

import { api } from "../../../lib/api";


import { type DataVariable, type Widget, type ZoneDef } from "../types";
import { PropField, PropInput, PropNumber } from "./PropFields";

/** P2-07 binding panel: widget instance + schema-driven config + data
 * variables ({{token}}) for dynamic text. */
export function WidgetZonePanel({
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
      widget: ref ? { ...ref, ...patch } : { widget_id: "", config: {}, bindings: {}, ...patch },
    });
  }

  return (
    <Space orientation="vertical" size="small" className="w-full dsc-border-t pt-3">
      <PropField label="Widget">
        <Select
          className="w-full"
          value={ref?.widget_id || undefined}
          placeholder="— choose widget —"
          allowClear
          disabled={disabled}
          onChange={(value) =>
            updateZone(zone.key, {
              widget: value ? { widget_id: value, config: {}, bindings: {} } : null,
            })
          }
          options={widgets.map((w) => ({ value: w.id, label: `${w.name} (${w.type})` }))}
          aria-label="Widget"
        />
      </PropField>

      {schema &&
        ref &&
        schema.fields.map((field) => {
          const value = ref.config?.[field.key];
          const set = (v: unknown) => patchWidget({ config: { ...ref.config, [field.key]: v } });
          if (field.type === "boolean") {
            return (
              <Checkbox
                key={field.key}
                checked={Boolean(value)}
                disabled={disabled}
                onChange={(e) => set(e.target.checked)}
              >
                {field.label ?? field.key}
                {field.required && <Typography.Text type="danger"> *</Typography.Text>}
              </Checkbox>
            );
          }
          if (field.type === "select") {
            return (
              <PropField
                key={field.key}
                label={`${field.label ?? field.key}${field.required ? " *" : ""}`}
              >
                <Select
                  className="w-full"
                  value={String(value ?? field.default ?? "") || undefined}
                  placeholder="— choose —"
                  disabled={disabled}
                  onChange={(v) => set(v)}
                  options={(field.options ?? []).map((option) => ({
                    value: option,
                    label: option,
                  }))}
                  aria-label={field.label ?? field.key}
                />
              </PropField>
            );
          }
          if (field.type === "number") {
            return (
              <PropNumber
                key={field.key}
                label={`${field.label ?? field.key}${field.required ? " *" : ""}`}
                value={Number(value ?? field.default ?? 0)}
                onChange={(v) => set(v)}
                disabled={disabled}
              />
            );
          }
          return (
            <PropInput
              key={field.key}
              label={`${field.label ?? field.key}${field.required ? " *" : ""}`}
              type={field.type === "color" ? "color" : "text"}
              value={String(value ?? field.default ?? "")}
              onChange={(v) => set(v)}
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
          <Typography.Text type="secondary" className="text-xs">
            Use {"{{token}}"} with approved variables:{" "}
            {(variablesQuery.data?.data ?? []).map((v) => v.token).join(", ")}
          </Typography.Text>
        </div>
      )}
      {ref && <DataBindingEditor refWidget={ref} patchWidget={patchWidget} disabled={disabled} />}
      {widget?.fallback_json && (
        <Typography.Text type="secondary" className="text-xs">
          Fallback when data unavailable: {JSON.stringify(widget.fallback_json)}
        </Typography.Text>
      )}
    </Space>
  );
}

/** P3-04 (3A-2): bind the widget to a live data source with a safe
 * declarative transform. The player receives validated snapshots via the
 * manifest `data` block — never a raw feed. */
export function DataBindingEditor({
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
    <Space orientation="vertical" size="small" className="w-full dsc-border-t pt-3">
      <PropField label="Live data source">
        <Select
          className="w-full"
          value={binding?.source_id || undefined}
          placeholder="— no live data —"
          allowClear
          disabled={disabled}
          onChange={(value) =>
            patchWidget({ data_binding: value ? { source_id: value } : null })
          }
          options={sources.map((s) => ({
            value: s.id,
            label: `${s.name}${s.state !== "active" ? ` (${s.state})` : ""}`,
          }))}
          aria-label="Live data source"
        />
      </PropField>
      {binding && (
        <>
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
          <PropNumber
            label="Item limit"
            value={transform.limit ?? null}
            onChange={(v) =>
              patchBinding({ transform: { ...transform, limit: v ?? undefined } })
            }
            disabled={disabled}
          />
          <Typography.Text type="secondary" className="text-xs">
            Snapshots are refreshed server-side; when the source is down the player keeps
            last-known-good, then the widget fallback.
          </Typography.Text>
        </>
      )}
    </Space>
  );
}
