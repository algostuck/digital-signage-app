import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Asset } from "../content/types";
import type { LayoutSummary } from "../design/types";
import { formatDuration, type PlaylistDetail, type PlaylistItem, type PlaylistSummary } from "./types";

const TRANSITIONS = ["none", "fade", "slide"];

/** SCR-18 Playlist Editor: sequencing, duration, transition, fallback. */
export function PlaylistEditorPage() {
  const { playlistId } = useParams<{ playlistId: string }>();
  const { hasPermission } = useAuth();
  const canManage = hasPermission("playlists.manage");
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const playlistQuery = useQuery({
    queryKey: ["playlist", playlistId],
    queryFn: () => api.get<PlaylistDetail>(`/playlists/${playlistId}`),
  });
  const fallbackOptionsQuery = useQuery({
    queryKey: ["playlists"],
    queryFn: () => api.get<PlaylistSummary[]>("/playlists?page_size=100"),
    enabled: canManage,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["playlist", playlistId] });
    queryClient.invalidateQueries({ queryKey: ["playlists"] });
  };
  const onError = (err: unknown) =>
    setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Action failed" });

  const patchPlaylist = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch(`/playlists/${playlistId}`, body),
    onSuccess: refresh,
    onError,
  });
  const patchItem = useMutation({
    mutationFn: ({ itemId, body }: { itemId: string; body: Record<string, unknown> }) =>
      api.patch(`/playlists/${playlistId}/items/${itemId}`, body),
    onSuccess: refresh,
    onError,
  });
  const removeItem = useMutation({
    mutationFn: (itemId: string) => api.delete(`/playlists/${playlistId}/items/${itemId}`),
    onSuccess: refresh,
    onError,
  });
  const publish = useMutation({
    mutationFn: () => api.post(`/playlists/${playlistId}/publish`),
    onSuccess: () => {
      refresh();
      setMessage({ kind: "ok", text: "Playlist published." });
    },
    onError,
  });

  const playlist = playlistQuery.data?.data ?? null;
  if (!playlist) return <Spinner label="Loading playlist…" />;

  const fallbackOptions = (fallbackOptionsQuery.data?.data ?? []).filter(
    (p) => p.id !== playlist.id,
  );

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/playlists" className="text-sm text-slate-500 hover:underline">
            ← Playlists
          </Link>
          <h1 className="text-xl font-semibold text-slate-900">
            {playlist.name}
            <span className="ml-3 align-middle">
              <StatusBadge status={playlist.status} />
            </span>
            {playlist.current_version_no && (
              <span className="ml-2 text-sm font-normal text-slate-400">
                v{playlist.current_version_no}
              </span>
            )}
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {playlist.items.length} items · {formatDuration(playlist.total_duration_ms)} total
          </p>
        </div>
        {canManage && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setAddOpen(true)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
            >
              Add item
            </button>
            <button
              type="button"
              onClick={() => publish.mutate()}
              disabled={publish.isPending}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {publish.isPending ? "Publishing…" : "Publish"}
            </button>
          </div>
        )}
      </div>

      {message && (
        <p
          role="alert"
          className={`mt-2 rounded-md px-3 py-2 text-sm ${
            message.kind === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </p>
      )}

      {canManage && (
        <div className="mt-3 flex flex-wrap items-center gap-4 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm">
          <label className="flex items-center gap-2 text-slate-600">
            <input
              type="checkbox"
              checked={playlist.loop_enabled}
              onChange={(e) => patchPlaylist.mutate({ loop_enabled: e.target.checked })}
            />
            Loop playback
          </label>
          <label className="flex items-center gap-2 text-slate-600">
            Fallback:
            <select
              value={playlist.fallback_playlist_id ?? ""}
              onChange={(e) =>
                patchPlaylist.mutate(
                  e.target.value
                    ? { fallback_playlist_id: e.target.value }
                    : { clear_fallback: true },
                )
              }
              className="rounded-md border border-slate-300 px-2 py-1"
            >
              <option value="">none</option>
              {fallbackOptions.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {playlist.items.length === 0 ? (
        <p className="mt-4 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No items yet. Add published content or layouts to build the sequence.
        </p>
      ) : (
        <ol className="mt-4 space-y-2">
          {playlist.items.map((item, index) => (
            <ItemRow
              key={item.id}
              item={item}
              index={index}
              total={playlist.items.length}
              canManage={canManage}
              onMove={(pos) => patchItem.mutate({ itemId: item.id, body: { position: pos } })}
              onDuration={(ms) =>
                patchItem.mutate({ itemId: item.id, body: { duration_ms: ms } })
              }
              onTransition={(t) =>
                patchItem.mutate({
                  itemId: item.id,
                  body: { transition: t === "none" ? {} : { type: t } },
                })
              }
              onToggle={(enabled) => patchItem.mutate({ itemId: item.id, body: { enabled } })}
              onRemove={() => removeItem.mutate(item.id)}
            />
          ))}
        </ol>
      )}

      {addOpen && (
        <AddItemModal
          playlistId={playlist.id}
          onClose={() => setAddOpen(false)}
          onAdded={() => {
            refresh();
            setAddOpen(false);
          }}
        />
      )}
    </div>
  );
}

function ItemRow({
  item,
  index,
  total,
  canManage,
  onMove,
  onDuration,
  onTransition,
  onToggle,
  onRemove,
}: {
  item: PlaylistItem;
  index: number;
  total: number;
  canManage: boolean;
  onMove: (position: number) => void;
  onDuration: (ms: number) => void;
  onTransition: (transition: string) => void;
  onToggle: (enabled: boolean) => void;
  onRemove: () => void;
}) {
  const [duration, setDuration] = useState(
    item.duration_ms != null ? String(item.duration_ms / 1000) : "",
  );

  return (
    <li
      className={`flex flex-wrap items-center gap-3 rounded-lg border bg-white px-4 py-3 ${
        item.enabled ? "border-slate-200" : "border-slate-200 opacity-50"
      }`}
    >
      <span className="w-6 text-center text-sm font-semibold text-slate-400">
        {item.position}
      </span>
      <div className="flex h-12 w-16 items-center justify-center overflow-hidden rounded bg-slate-100">
        {item.thumbnail_url ? (
          <img src={item.thumbnail_url} alt="" className="h-full w-full object-cover" />
        ) : (
          <span className="text-xs uppercase text-slate-400">
            {item.item_type === "layout" ? "layout" : item.asset_type ?? "?"}
          </span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-slate-800">{item.name}</p>
        <p className="text-xs text-slate-500">
          {item.item_type}
          {!item.ready && <span className="ml-2 text-red-600">not ready</span>}
        </p>
      </div>
      {canManage ? (
        <>
          <label className="flex items-center gap-1 text-xs text-slate-500">
            sec
            <input
              type="number"
              min={1}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              onBlur={() => {
                const seconds = Number(duration);
                if (seconds > 0 && seconds * 1000 !== item.duration_ms) {
                  onDuration(Math.round(seconds * 1000));
                }
              }}
              className="w-16 rounded-md border border-slate-300 px-2 py-1 text-sm"
              aria-label={`Duration for ${item.name}`}
            />
          </label>
          <select
            value={item.transition_json?.type ?? "none"}
            onChange={(e) => onTransition(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
            aria-label={`Transition for ${item.name}`}
          >
            {TRANSITIONS.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled={index === 0}
              onClick={() => onMove(item.position - 1)}
              aria-label={`Move ${item.name} up`}
              className="rounded border border-slate-300 px-2 py-1 text-xs disabled:opacity-30"
            >
              ↑
            </button>
            <button
              type="button"
              disabled={index === total - 1}
              onClick={() => onMove(item.position + 1)}
              aria-label={`Move ${item.name} down`}
              className="rounded border border-slate-300 px-2 py-1 text-xs disabled:opacity-30"
            >
              ↓
            </button>
            <button
              type="button"
              onClick={() => onToggle(!item.enabled)}
              className="rounded border border-slate-300 px-2 py-1 text-xs"
            >
              {item.enabled ? "Disable" : "Enable"}
            </button>
            <button
              type="button"
              onClick={onRemove}
              className="rounded border border-red-200 px-2 py-1 text-xs text-red-600"
            >
              Remove
            </button>
          </div>
        </>
      ) : (
        <span className="text-sm text-slate-500">
          {item.duration_ms != null ? formatDuration(item.duration_ms) : "natural"}
        </span>
      )}
    </li>
  );
}

function AddItemModal({
  playlistId,
  onClose,
  onAdded,
}: {
  playlistId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [kind, setKind] = useState<"asset" | "layout">("asset");
  const [refId, setRefId] = useState("");
  const [seconds, setSeconds] = useState("8");
  const [error, setError] = useState<string | null>(null);

  const assetsQuery = useQuery({
    queryKey: ["assets-for-playlist"],
    queryFn: () => api.get<Asset[]>("/assets?page_size=100"),
  });
  const layoutsQuery = useQuery({
    queryKey: ["layouts-for-playlist"],
    queryFn: () => api.get<LayoutSummary[]>("/layouts?status=published&page_size=100"),
  });

  const readyAssets = (assetsQuery.data?.data ?? []).filter(
    (a) => a.current_version?.processing_status === "ready",
  );
  const layouts = layoutsQuery.data?.data ?? [];

  const add = useMutation({
    mutationFn: () =>
      api.post(`/playlists/${playlistId}/items`, {
        asset_id: kind === "asset" ? refId : undefined,
        layout_id: kind === "layout" ? refId : undefined,
        duration_ms: Number(seconds) > 0 ? Math.round(Number(seconds) * 1000) : undefined,
      }),
    onSuccess: onAdded,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to add item"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!refId) {
      setError("Choose an item to add");
      return;
    }
    setError(null);
    add.mutate();
  }

  const options = kind === "asset" ? readyAssets : layouts;

  return (
    <Modal title="Add playlist item" open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <div className="flex gap-2" role="radiogroup" aria-label="Item kind">
          {(["asset", "layout"] as const).map((k) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={kind === k}
              onClick={() => {
                setKind(k);
                setRefId("");
              }}
              className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize ${
                kind === k ? "bg-slate-900 text-white" : "border border-slate-300 text-slate-600"
              }`}
            >
              {k}
            </button>
          ))}
        </div>
        <div>
          <label htmlFor="item-ref" className="block text-sm font-medium text-slate-700">
            {kind === "asset" ? "Content (READY only)" : "Layout (published only)"}
          </label>
          <select
            id="item-ref"
            value={refId}
            onChange={(e) => setRefId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">— choose —</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="item-duration" className="block text-sm font-medium text-slate-700">
            Duration (seconds)
          </label>
          <input
            id="item-duration"
            type="number"
            min={1}
            value={seconds}
            onChange={(e) => setSeconds(e.target.value)}
            className="mt-1 block w-32 rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
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
            disabled={add.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {add.isPending ? "Adding…" : "Add item"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
