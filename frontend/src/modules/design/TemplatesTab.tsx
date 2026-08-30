import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { FormField } from "../../components/ui/FormField";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../devices/types";
import type { Template } from "./types";

/** P2-06 Template Library: versions, approval status, reuse. */
export function TemplatesTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("layouts.manage");
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.get<Template[]>("/templates"),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["templates"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const submit = useMutation({
    mutationFn: (id: string) => api.post(`/templates/${id}/submit`, {}),
    onSuccess: () => {
      refresh();
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      setError(null);
    },
    onError,
  });
  const archive = useMutation({
    mutationFn: (id: string) => api.delete(`/templates/${id}`),
    onSuccess: refresh,
    onError,
  });
  const clone = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      api.post<{ id: string }>(`/templates/${id}/clone`, { name }),
    onSuccess: (envelope) => navigate(`/design/${envelope.data!.id}`),
    onError,
  });

  const templates = (templatesQuery.data?.data ?? []).filter(
    (t) => t.status !== "archived",
  );

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          Governed, versioned design assets. Submissions go through the approval inbox.
        </p>
        {canManage && (
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
          >
            New template
          </button>
        )}
      </div>

      {error && (
        <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}

      {templatesQuery.isLoading ? (
        <Spinner label="Loading templates…" />
      ) : templates.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No templates yet. Create one from scratch, or save a layout as a template
          from the designer.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <div key={template.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between gap-2">
                <p className="font-medium text-slate-800">{template.name}</p>
                <StatusBadge status={template.status} />
              </div>
              <p className="mt-1 text-sm text-slate-500">
                {template.canvas_json.zones.length} zone
                {template.canvas_json.zones.length === 1 ? "" : "s"}
                {template.current_version_no
                  ? ` · v${template.current_version_no} approved`
                  : " · no approved version"}
                {" · "}updated {timeAgo(template.updated_at)}
              </p>
              {template.description && (
                <p className="mt-1 text-xs text-slate-400">{template.description}</p>
              )}
              {canManage && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {(template.status === "draft" || template.status === "rejected") && (
                    <button
                      type="button"
                      onClick={() => submit.mutate(template.id)}
                      className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white"
                    >
                      Submit for approval
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      const name = window.prompt(
                        "Name for the new layout cloned from this template:",
                        `${template.name} copy`,
                      );
                      if (name) clone.mutate({ id: template.id, name });
                    }}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600"
                  >
                    Use in layout
                  </button>
                  {template.status !== "pending_approval" && (
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`Archive template "${template.name}"?`)) {
                          archive.mutate(template.id);
                        }
                      }}
                      className="rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600"
                    >
                      Archive
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {createOpen && (
        <CreateTemplateModal
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

function CreateTemplateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api.post("/templates", { name, description: description || null }),
    onSuccess: onCreated,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create template"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <Modal title="New template" open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <FormField
          id="template-name"
          label="Name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <FormField
          id="template-description"
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <p className="text-xs text-slate-400">
          Starts as a blank 1920×1080 draft. You can also save an existing layout as
          a template from the designer.
        </p>
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
            {create.isPending ? "Creating…" : "Create template"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
