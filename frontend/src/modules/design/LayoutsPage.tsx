import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { FormField } from "../../components/ui/FormField";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { AiStudioTab } from "./AiStudioTab";
import { TemplatesTab } from "./TemplatesTab";
import { WidgetsTab } from "./WidgetsTab";
import type { LayoutDetail, LayoutSummary, Template } from "./types";

const TABS = [
  { key: "layouts", label: "Layouts" },
  { key: "templates", label: "Templates" },
  { key: "widgets", label: "Widgets" },
  { key: "ai", label: "AI Studio" },
] as const;

/** Design studio: SCR-15 layouts + P2-06 templates + P2-08 widgets. */
export function LayoutsPage() {
  const [tab, setTab] = useState<string>("layouts");

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Design</h1>
      <div className="mt-4 border-b border-slate-200" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t.key
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-4">
        {tab === "layouts" ? (
          <LayoutsTab />
        ) : tab === "templates" ? (
          <TemplatesTab />
        ) : tab === "widgets" ? (
          <WidgetsTab />
        ) : (
          <AiStudioTab />
        )}
      </div>
    </div>
  );
}

function LayoutsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("layouts.manage");
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);

  const layoutsQuery = useQuery({
    queryKey: ["layouts"],
    queryFn: () => api.get<LayoutSummary[]>("/layouts?page_size=100"),
  });

  const layouts = layoutsQuery.data?.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">Screen compositions with generic zones.</p>
        {canManage && (
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            New layout
          </button>
        )}
      </div>

      {layoutsQuery.isLoading ? (
        <Spinner label="Loading layouts…" />
      ) : layouts.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No layouts yet. Create one from scratch or from a template.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {layouts.map((layout) => (
            <button
              key={layout.id}
              type="button"
              onClick={() => navigate(`/design/${layout.id}`)}
              className="rounded-lg border border-slate-200 bg-white p-4 text-left transition-shadow hover:shadow-md"
            >
              <div className="flex items-start justify-between">
                <p className="font-medium text-slate-800">{layout.name}</p>
                <StatusBadge status={layout.status} />
              </div>
              <p className="mt-1 text-sm text-slate-500">
                {layout.zone_count} zone{layout.zone_count === 1 ? "" : "s"}
                {layout.current_version_no ? ` · v${layout.current_version_no} published` : " · never published"}
              </p>
            </button>
          ))}
        </div>
      )}

      {createOpen && (
        <CreateLayoutModal
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => navigate(`/design/${id}`)}
        />
      )}
    </div>
  );
}

function CreateLayoutModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.get<Template[]>("/templates"),
  });

  const create = useMutation({
    mutationFn: () =>
      templateId
        ? api.post<LayoutDetail>(`/templates/${templateId}/clone`, { name })
        : api.post<LayoutDetail>("/layouts", { name }),
    onSuccess: (envelope) => {
      queryClient.invalidateQueries({ queryKey: ["layouts"] });
      onCreated(envelope.data!.id);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create layout"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <Modal title="New layout" open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <FormField
          id="layout-name"
          label="Name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <div>
          <label htmlFor="layout-template" className="block text-sm font-medium text-slate-700">
            Start from
          </label>
          <select
            id="layout-template"
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm"
          >
            <option value="">Blank 1920×1080</option>
            {(templatesQuery.data?.data ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                Template: {t.name}
              </option>
            ))}
          </select>
        </div>
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
            {create.isPending ? "Creating…" : "Create & open designer"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
