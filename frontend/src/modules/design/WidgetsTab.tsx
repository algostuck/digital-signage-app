import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { FormField } from "../../components/ui/FormField";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Widget, WidgetSchemaField } from "./types";

const FIELD_TYPES = ["string", "number", "boolean", "select", "url", "color"] as const;

/** P2-08 Widget Library: schema-driven catalogue with versions + fallback. */
export function WidgetsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("widgets.manage");
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const widgetsQuery = useQuery({
    queryKey: ["widgets"],
    queryFn: () => api.get<Widget[]>("/widgets"),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["widgets"] });

  const archive = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.patch(`/widgets/${id}`, { status }),
    onSuccess: refresh,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Action failed"),
  });

  const widgets = widgetsQuery.data?.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          Schema-driven widgets with fallback content. Zones bind them via the
          designer's widget panel.
        </p>
        {canManage && (
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
          >
            New widget
          </button>
        )}
      </div>

      {error && (
        <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      {widgetsQuery.isLoading ? (
        <Spinner label="Loading widgets…" />
      ) : widgets.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No widgets yet. Create one to make it configurable inside layout zones.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {widgets.map((widget) => {
            const current = widget.versions[widget.versions.length - 1];
            return (
              <div key={widget.id} className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-medium text-slate-800">{widget.name}</p>
                  <StatusBadge status={widget.status} />
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  {widget.type} · schema v{current?.version_no ?? "?"}
                  {widget.fallback_json ? " · fallback set" : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {(current?.config_schema_json.fields ?? []).map((field) => (
                    <span
                      key={field.key}
                      className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                      title={`${field.type}${field.required ? " · required" : ""}`}
                    >
                      {field.key}
                    </span>
                  ))}
                </div>
                {canManage && (
                  <div className="mt-3">
                    <button
                      type="button"
                      onClick={() =>
                        archive.mutate({
                          id: widget.id,
                          status: widget.status === "active" ? "archived" : "active",
                        })
                      }
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600"
                    >
                      {widget.status === "active" ? "Archive" : "Restore"}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {createOpen && (
        <CreateWidgetModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            refresh();
            setCreateOpen(false);
          }}
        />
      )}
    </div>
  );
}

interface FieldDraft {
  key: string;
  label: string;
  type: (typeof FIELD_TYPES)[number];
  required: boolean;
  options: string;
}

function CreateWidgetModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState("clock");
  const [fallbackText, setFallbackText] = useState("");
  const [fields, setFields] = useState<FieldDraft[]>([
    { key: "text", label: "Text", type: "string", required: false, options: "" },
  ]);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => {
      const schemaFields: WidgetSchemaField[] = fields.map((f) => ({
        key: f.key.trim(),
        label: f.label.trim() || f.key.trim(),
        type: f.type,
        required: f.required,
        ...(f.type === "select"
          ? { options: f.options.split(",").map((o) => o.trim()).filter(Boolean) }
          : {}),
      }));
      return api.post("/widgets", {
        type,
        name,
        config_schema_json: { fields: schemaFields },
        fallback_json: fallbackText ? { text: fallbackText } : null,
      });
    },
    onSuccess: onCreated,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create widget"),
  });

  function setField(index: number, patch: Partial<FieldDraft>) {
    setFields((prev) => prev.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <Modal title="New widget" open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <div className="grid grid-cols-2 gap-3">
          <FormField
            id="widget-name"
            label="Name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div>
            <label htmlFor="widget-type" className="block text-sm font-medium text-slate-700">
              Type
            </label>
            <input
              id="widget-type"
              value={type}
              onChange={(e) => setType(e.target.value)}
              placeholder="clock, weather, ticker…"
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div>
          <p className="text-sm font-medium text-slate-700">Configuration fields</p>
          <div className="mt-2 space-y-2">
            {fields.map((field, index) => (
              <div key={index} className="flex flex-wrap items-center gap-2">
                <input
                  value={field.key}
                  onChange={(e) => setField(index, { key: e.target.value })}
                  placeholder="key"
                  aria-label={`Field ${index + 1} key`}
                  className="w-28 rounded-md border border-slate-300 px-2 py-1.5 text-sm font-mono"
                />
                <select
                  value={field.type}
                  onChange={(e) =>
                    setField(index, { type: e.target.value as FieldDraft["type"] })
                  }
                  aria-label={`Field ${index + 1} type`}
                  className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                >
                  {FIELD_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                {field.type === "select" && (
                  <input
                    value={field.options}
                    onChange={(e) => setField(index, { options: e.target.value })}
                    placeholder="options, comma-separated"
                    aria-label={`Field ${index + 1} options`}
                    className="w-44 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  />
                )}
                <label className="flex items-center gap-1 text-xs text-slate-500">
                  <input
                    type="checkbox"
                    checked={field.required}
                    onChange={(e) => setField(index, { required: e.target.checked })}
                  />
                  required
                </label>
                {fields.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setFields((prev) => prev.filter((_, i) => i !== index))}
                    className="text-xs text-red-600"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() =>
              setFields((prev) => [
                ...prev,
                { key: "", label: "", type: "string", required: false, options: "" },
              ])
            }
            className="mt-2 text-sm font-medium text-slate-600 underline"
          >
            + Add field
          </button>
        </div>

        <FormField
          id="widget-fallback"
          label="Fallback text (shown when data is unavailable)"
          value={fallbackText}
          onChange={(e) => setFallbackText(e.target.value)}
        />

        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={create.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create widget"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
