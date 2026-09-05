import { CloudUploadOutlined, CopyOutlined, DeleteOutlined, DesktopOutlined, PlusOutlined, SaveOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Breadcrumb, Button, Card, Col, Flex, Input, Modal, Popconfirm, Row, Select, Space, Typography } from "antd";
import { ToneTag } from "@/design-system";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Asset } from "../content/types";
import { CompositionTVPreview } from "../preview";
import { PropField, PropInput, PropNumber } from "./designer/PropFields";
import { WidgetZonePanel } from "./designer/WidgetZonePanel";
import { newZoneKey, ZONE_CONTENT_TYPES, type LayoutCanvas, type LayoutDetail, type ZoneDef } from "./types";

/** Stage sizing. The canvas is scaled to fit the space it actually has —
 * a 1920×1080 layout in a fixed-width stage overflowed its card and put
 * scrollbars between the designer and the artboard. Width comes from the
 * column, height from what is left below the fold, and the smaller of the
 * two ratios wins so the whole artboard is always visible at once. */
const STAGE_FALLBACK_WIDTH = 820;
const STAGE_MIN_HEIGHT = 320;
/** Room under the stage for its caption and the page's bottom gutter. */
const STAGE_BOTTOM_GUTTER = 104;

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
  const [previewOpen, setPreviewOpen] = useState(false);
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

  const stageBoxRef = useRef<HTMLDivElement>(null);
  const [stageBox, setStageBox] = useState({ width: STAGE_FALLBACK_WIDTH, height: 480 });

  useEffect(() => {
    const el = stageBoxRef.current;
    if (!el) return;
    const measure = () => {
      const rect = el.getBoundingClientRect();
      // Document-relative top, so the measurement does not drift as the
      // page is scrolled.
      const top = rect.top + window.scrollY;
      const next = {
        width: Math.max(1, el.clientWidth),
        height: Math.max(STAGE_MIN_HEIGHT, window.innerHeight - top - STAGE_BOTTOM_GUTTER),
      };
      setStageBox((prev) => (prev.width === next.width && prev.height === next.height ? prev : next));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [canvas]);

  // Fit, never upscale: a small artboard stays at 100 % rather than being
  // blown up past its own resolution.
  const scale = canvas
    ? Math.min(stageBox.width / canvas.canvas.width, stageBox.height / canvas.canvas.height, 1)
    : 1;

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
            <Typography.Title level={3} style={{ marginBottom: 0 }}>
              {layout.name}
            </Typography.Title>
            <StatusBadge status={layout.status} />
            {dirty && (
              <ToneTag tone="warning">
                Unsaved changes
              </ToneTag>
            )}
          </Space>
        </div>
        <Space wrap>
          {/* Read-only, so it is not gated behind manage permission. */}
          <Button icon={<DesktopOutlined />} onClick={() => setPreviewOpen(true)}>
            Preview
          </Button>
          {canManage && (
            <>
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
            </>
          )}
        </Space>
      </Flex>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={17}>
          <Card size="small" styles={{ body: { background: "#f1f5f9", overflow: "hidden" } }}>
            <div ref={stageBoxRef} className="w-full">
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
            </div>
            <Typography.Paragraph type="secondary" className="mt-2 text-center text-xs" style={{ marginBottom: 0 }}>
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

      <CompositionTVPreview
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        title={`Preview — ${layout.name}`}
        canvas={canvas}
      />
    </div>
  );
}

