import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { LocationDetail } from "./types";

interface Props {
  detail: LocationDetail;
  canManage: boolean;
  onSaved: () => void;
}

/** Inline key=value tag editor with replace-set save semantics. */
export function TagEditor({ detail, canManage, onSaved }: Props) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (tags: { key: string; value: string }[]) =>
      api.post(`/locations/${detail.id}/tags`, { tags }),
    onSuccess: onSaved,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to save tags"),
  });

  function currentTags() {
    return detail.tags.map((t) => ({ key: t.key, value: t.value }));
  }

  function addTag() {
    setError(null);
    const match = draft.match(/^\s*([^=]+?)\s*=\s*(.+?)\s*$/);
    if (!match) {
      setError("Use key=value format, e.g. tier=premium");
      return;
    }
    save.mutate([...currentTags(), { key: match[1], value: match[2] }]);
    setDraft("");
  }

  function removeTag(key: string, value: string) {
    save.mutate(currentTags().filter((t) => !(t.key === key && t.value === value)));
  }

  return (
    <div>
      <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">Tags</h3>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {detail.tags.length === 0 && <span className="text-sm text-slate-400">No tags</span>}
        {detail.tags.map((t) => (
          <span
            key={t.id}
            className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700"
          >
            {t.key}={t.value}
            {canManage && (
              <button
                type="button"
                aria-label={`Remove tag ${t.key}=${t.value}`}
                onClick={() => removeTag(t.key, t.value)}
                className="text-slate-400 hover:text-red-600"
              >
                ✕
              </button>
            )}
          </span>
        ))}
      </div>
      {canManage && (
        <div className="mt-3 flex gap-2">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addTag();
              }
            }}
            placeholder="key=value"
            aria-label="New tag"
            className="w-48 rounded-md border border-slate-300 px-3 py-1.5 text-sm shadow-sm"
          />
          <button
            type="button"
            onClick={addTag}
            disabled={save.isPending}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 disabled:opacity-50"
          >
            Add tag
          </button>
        </div>
      )}
      {error && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
