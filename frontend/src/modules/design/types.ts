export interface ZoneDef {
  key: string;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  z_index: number;
  rotation: number;
  style: Record<string, unknown>;
  content_type: string;
  content_config: Record<string, unknown>;
  widget?: {
    widget_id: string;
    config?: Record<string, unknown>;
    bindings?: Record<string, string>;
  } | null;
}

export interface LayoutCanvas {
  schema_version: number;
  canvas: {
    width: number;
    height: number;
    background: string | null;
    orientation: "landscape" | "portrait";
  };
  zones: ZoneDef[];
}

export interface LayoutSummary {
  id: string;
  name: string;
  description: string | null;
  status: string;
  current_version_id: string | null;
  current_version_no: number | null;
  zone_count: number;
  created_at: string;
  updated_at: string;
}

export interface LayoutDetail extends LayoutSummary {
  draft_canvas_json: LayoutCanvas;
  versions: { id: string; version_no: number; published_at: string }[];
}

export interface Template {
  id: string;
  layout_id: string | null;
  name: string;
  description: string | null;
  canvas_json: LayoutCanvas;
  status: string;
  current_version_no: number | null;
  created_at: string;
  updated_at: string;
}

export interface WidgetSchemaField {
  key: string;
  label?: string;
  type: "string" | "number" | "boolean" | "select" | "url" | "color";
  required?: boolean;
  options?: string[];
  default?: unknown;
}

export interface WidgetVersion {
  id: string;
  version_no: number;
  config_schema_json: { fields: WidgetSchemaField[] };
  defaults_json: Record<string, unknown> | null;
}

export interface Widget {
  id: string;
  type: string;
  name: string;
  status: string;
  fallback_json: Record<string, unknown> | null;
  created_at: string;
  versions: WidgetVersion[];
}

export interface DataVariable {
  token: string;
  label: string;
}

export const ZONE_CONTENT_TYPES = [
  "placeholder",
  "image",
  "video",
  "playlist",
  "text",
  "ticker",
  "clock",
  "web",
  "widget",
  "qr",
] as const;

export function newZoneKey(existing: string[]): string {
  let index = existing.length + 1;
  while (existing.includes(`zone-${index}`)) index += 1;
  return `zone-${index}`;
}
