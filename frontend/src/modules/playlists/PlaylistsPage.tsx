import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { FormField } from "../../components/ui/FormField";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDuration, type PlaylistDetail, type PlaylistSummary } from "./types";

/** SCR-17 Playlists. */
export function PlaylistsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("playlists.manage");
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);

  const playlistsQuery = useQuery({
    queryKey: ["playlists"],
    queryFn: () => api.get<PlaylistSummary[]>("/playlists?page_size=100"),
  });

  const playlists = playlistsQuery.data?.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Playlists</h1>
        {canManage && (
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            New playlist
          </button>
        )}
      </div>

      {playlistsQuery.isLoading ? (
        <Spinner label="Loading playlists…" />
      ) : playlists.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No playlists yet. A playlist is an ordered sequence of content or layouts.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {playlists.map((playlist) => (
            <button
              key={playlist.id}
              type="button"
              onClick={() => navigate(`/playlists/${playlist.id}`)}
              className="rounded-lg border border-slate-200 bg-white p-4 text-left transition-shadow hover:shadow-md"
            >
              <div className="flex items-start justify-between">
                <p className="font-medium text-slate-800">{playlist.name}</p>
                <StatusBadge status={playlist.status} />
              </div>
              <p className="mt-1 text-sm text-slate-500">
                {playlist.item_count} item{playlist.item_count === 1 ? "" : "s"} ·{" "}
                {formatDuration(playlist.total_duration_ms)}
                {playlist.loop_enabled ? " · loops" : ""}
                {playlist.current_version_no ? ` · v${playlist.current_version_no}` : ""}
              </p>
            </button>
          ))}
        </div>
      )}

      {createOpen && (
        <CreatePlaylistModal
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => navigate(`/playlists/${id}`)}
        />
      )}
    </div>
  );
}

function CreatePlaylistModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => api.post<PlaylistDetail>("/playlists", { name }),
    onSuccess: (envelope) => {
      queryClient.invalidateQueries({ queryKey: ["playlists"] });
      onCreated(envelope.data!.id);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create playlist"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <Modal title="New playlist" open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <FormField
          id="playlist-name"
          label="Name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
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
            {create.isPending ? "Creating…" : "Create & open editor"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
