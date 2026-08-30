import { useMutation } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { Modal } from "../../components/ui/Modal";
import { api, ApiError } from "../../lib/api";
import type { LocationDetail, LocationNode, TreeEntry } from "./types";

interface Props {
  detail: LocationDetail;
  tree: TreeEntry[];
  onClose: () => void;
  onSaved: () => void;
}

function flatten(entries: TreeEntry[], out: LocationNode[] = []): LocationNode[] {
  for (const entry of entries) {
    out.push(entry.node);
    flatten(entry.children, out);
  }
  return out;
}

const NBSP = " ";

export function MoveLocationModal({ detail, tree, onClose, onSaved }: Props) {
  const [newParentId, setNewParentId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  // A node cannot move under itself or anything in its own subtree.
  const candidates = useMemo(
    () =>
      flatten(tree).filter(
        (n) => !n.path.startsWith(detail.path) && n.id !== detail.parent_id,
      ),
    [tree, detail],
  );

  const move = useMutation({
    mutationFn: () =>
      api.post(`/locations/${detail.id}/move`, { new_parent_id: newParentId || null }),
    onSuccess: onSaved,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to move location"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    move.mutate();
  }

  return (
    <Modal title={`Move: ${detail.name}`} open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <div>
          <label htmlFor="move-parent" className="block text-sm font-medium text-slate-700">
            New parent
          </label>
          <select
            id="move-parent"
            value={newParentId}
            onChange={(e) => setNewParentId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm"
          >
            <option value="">(root, no parent)</option>
            {candidates.map((n) => (
              <option key={n.id} value={n.id}>
                {/* NBSP indentation: plain spaces collapse inside <option>. */}
                {(NBSP + NBSP).repeat(n.depth) + n.name}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-slate-500">
            The location's own subtree is excluded to prevent cycles.
          </p>
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
            disabled={move.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {move.isPending ? "Moving…" : "Move location"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
