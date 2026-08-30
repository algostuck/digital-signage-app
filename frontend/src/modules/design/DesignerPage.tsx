import {
  CloudUploadOutlined,
  CopyOutlined,
  DeleteOutlined,
  PlusOutlined,
  SaveOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Breadcrumb,
  Button,
  Card,
  Checkbox,
  Col,
  Flex,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LoadingState } from "../../components/ui/states";
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

/** SCR-16 Screen Designer: canvas, zones, drag/resize, properties, publish.
 * The canvas interaction layer (drag/resize/scale) is intentionally custom —
 * antd has no composition-canvas primitive; only the surrounding chrome uses
 * the design system. */
export function DesignerPage() {
  const { layoutId } = useParams<{ layoutId: string }>();
  const { hasPermission } = useAuth();
  const { message: toast } = App.useApp();
  const canManage = hasPermission("layouts.manage");
  const queryClient = useQueryClient();

  const [canvas, setCanvas] = useState<LayoutCanvas | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [templateName, setTemplateName] = useState("");
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
      toast.success("Draft saved.");
      queryClient.invalidateQueries({ queryKey: ["layout", layoutId] });
      queryClient.invalidateQueries({ queryKey: ["layouts"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Failed to save draft"),
  });

  const publish = useMutation({
    mutationFn: async () => {
      if (dirty) await api.patch(`/layouts/${layoutId}`, { canvas_json: canvas });
      return api.post(`/layouts/${layoutId}/publish`);
    },
    onSuccess: () => {
      setDirty(false);
      toast.success("Layout published.");
      queryClient.invalidateQueries({ queryKey: ["layout", layoutId] });
      queryClient.invalidateQueries({ queryKey: ["layouts"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Failed to publish"),
  });

  const saveAsTemplate = useMutation({
    mutationFn: (name: string) => api.post("/templates", { layout_id: layoutId, name }),
    onSuccess: () => {
      toast.success("Saved as a draft template (Design → Templates).");
      setTemplateModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["templates"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Failed to save template"),
  });

  if (layoutQuery.isLoading || !canvas || !layout) {
    return <LoadingState rows={8} />;
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
      <Flex wrap justify="space-between" align="flex-start" gap="small" className="mb-4">
        <div>
          <Breadcrumb
            className="mb-1"
            items={[
              { title: <Link to="/design">Design</Link> },
              { title: layout.name },
            ]}
          />
          <Space align="center">
            <Typography.Title level={3} className="!mb-0">
              {layout.name}
            </Typography.Title>
            <StatusBadge status={layout.status} />
            {dirty && (
              <Tag color="warning" variant="filled">
                Unsaved changes
              </Tag>
            )}
          </Space>
        </div>
        {canManage && (
          <Space wrap>
            <Button icon={<PlusOutlined />} onClick={addZone}>
              Add zone
            </Button>
            <Button
              icon={<SaveOutlined />}
              disabled={!dirty}
              loading={save.isPending}
              onClick={() => save.mutate()}
            >
              Save draft
            </Button>
            <Button
              icon={<CopyOutlined />}
              loading={saveAsTemplate.isPending}
              onClick={() => {
                setTemplateName(`${layout.name} template`);
                setTemplateModalOpen(true);
              }}
            >
              Save as template
            </Button>
            <Button
              type="primary"
              icon={<CloudUploadOutlined />}
              loading={publish.isPending}
              onClick={() => publish.mutate()}
            >
              Publish
            </Button>
          </Space>
        )}
      </Flex>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={17}>
          <Card size="small" styles={{ body: { background: "#f1f5f9", overflow: "auto" } }}>
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
            <Typography.Paragraph type="secondary" className="!mb-0 mt-2 text-center text-xs">
              {canvas.canvas.width}×{canvas.canvas.height} · scale {(scale * 100).toFixed(0)}%
            </Typography.Paragraph>
          </Card>
        </Col>

        <Col xs={24} xl={7}>
          <Card size="small" title={selected ? selected.name : "Properties"}>
            {!selected ? (
              <Typography.Text type="secondary">
                Select a zone on the canvas to edit its properties.
              </Typography.Text>
            ) : (
              <Space orientation="vertical" size="small" className="w-full">
                {canManage && (
                  <Space>
                    <Button
                      size="small"
                      icon={<CopyOutlined />}
                      onClick={() => duplicateZone(selected)}
                    >
                      Duplicate
                    </Button>
                    <Popconfirm
                      title={`Delete zone "${selected.name}"?`}
                      onConfirm={() => deleteZone(selected.key)}
                      okButtonProps={{ danger: true }}
                    >
                      <Button size="small" danger icon={<DeleteOutlined />}>
                        Delete
                      </Button>
                    </Popconfirm>
                  </Space>
                )}
                <PropInput
                  label="Name"
                  value={selected.name}
                  onChange={(v) => updateZone(selected.key, { name: v })}
                  disabled={!canManage}
                />
                <Row gutter={8}>
                  {(["x", "y", "width", "height"] as const).map((prop) => (
                    <Col span={12} key={prop}>
                      <PropNumber
                        label={prop}
                        value={Math.round(selected[prop])}
                        onChange={(v) =>
                          updateZone(selected.key, { [prop]: Math.max(0, v ?? 0) })
                        }
                        disabled={!canManage}
                      />
                    </Col>
                  ))}
                </Row>
                <PropNumber
                  label="Z-index"
                  value={selected.z_index}
                  onChange={(v) => updateZone(selected.key, { z_index: v ?? 0 })}
                  disabled={!canManage}
                />
                <PropInput
                  label="Background (CSS color)"
                  value={String(selected.style.background ?? "")}
                  onChange={(v) =>
                    updateZone(selected.key, {
                      style: { ...selected.style, background: v || null },
                    })
                  }
                  disabled={!canManage}
                />
                <PropField label="Content type">
                  <Select
                    className="w-full"
                    value={selected.content_type}
                    disabled={!canManage}
                    onChange={(value) =>
                      updateZone(selected.key, { content_type: value, content_config: {} })
                    }
                    options={ZONE_CONTENT_TYPES.map((t) => ({ value: t, label: t }))}
                    aria-label="Content type"
                  />
                </PropField>
                {(selected.content_type === "image" || selected.content_type === "video") && (
                  <PropField label="Asset">
                    <Select
                      className="w-full"
                      value={String(selected.content_config.asset_id ?? "") || undefined}
                      placeholder="— choose —"
                      allowClear
                      disabled={!canManage}
                      onChange={(value) =>
                        updateZone(selected.key, {
                          content_config: value ? { asset_id: value } : {},
                        })
                      }
                      options={assets
                        .filter((a) => a.type === selected.content_type)
                        .map((a) => ({ value: a.id, label: a.name }))}
                      aria-label="Asset"
                    />
                  </PropField>
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
                  <WidgetZonePanel zone={selected} updateZone={updateZone} disabled={!canManage} />
                )}
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title="Save as template"
        open={templateModalOpen}
        okText="Save template"
        confirmLoading={saveAsTemplate.isPending}
        onOk={() => {
          if (templateName.trim()) saveAsTemplate.mutate(templateName.trim());
        }}
        onCancel={() => setTemplateModalOpen(false)}
        destroyOnHidden
      >
        <Input
          autoFocus
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value)}
          placeholder="Template name"
          aria-label="Template name"
          onPressEnter={() => {
            if (templateName.trim()) saveAsTemplate.mutate(templateName.trim());
          }}
        />
      </Modal>
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
      widget: ref ? { ...ref, ...patch } : { widget_id: "", config: {}, bindings: {}, ...patch },
    });
  }

  return (
    <Space orientation="vertical" size="small" className="w-full border-t border-slate-200 pt-3">
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
    <Space orientation="vertical" size="small" className="w-full border-t border-slate-200 pt-3">
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

function PropField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Typography.Text type="secondary" className="block text-xs font-medium uppercase">
        {label}
      </Typography.Text>
      <div className="mt-1">{children}</div>
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
    <PropField label={label}>
      <Input
        type={type}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
      />
    </PropField>
  );
}

function PropNumber({
  label,
  value,
  onChange,
  disabled = false,
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  disabled?: boolean;
}) {
  return (
    <PropField label={label}>
      <InputNumber
        className="w-full"
        value={value}
        disabled={disabled}
        onChange={onChange}
        aria-label={label}
      />
    </PropField>
  );
}
