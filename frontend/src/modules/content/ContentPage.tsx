import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { AssetDetailModal } from "./AssetDetailModal";
import { UploadModal } from "./UploadModal";
import { formatBytes, type Asset, type Folder } from "./types";

const TYPE_FILTERS = ["", "image", "video", "audio", "document", "html", "text", "data"];

/** SCR-11 Content Library: folders, filters, grid, lifecycle. */
export function ContentPage() {
  const { hasPermission } = useAuth();
  const canCreate = hasPermission("content.create");
  const canDelete = hasPermission("content.delete");
  const queryClient = useQueryClient();

  const [folderId, setFolderId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const pageSize = 24;

  const foldersQuery = useQuery({
    queryKey: ["folders"],
    queryFn: () => api.get<Folder[]>("/folders"),
  });

  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set("q", search);
  if (typeFilter) params.set("type", typeFilter);
  if (folderId) params.set("folder_id", folderId);

  const assetsQuery = useQuery({
    queryKey: ["assets", params.toString()],
    queryFn: () => api.get<Asset[]>(`/assets?${params.toString()}`),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["assets"] });
    queryClient.invalidateQueries({ queryKey: ["folders"] });
  };

  const createFolder = useMutation({
    mutationFn: (name: string) => api.post("/folders", { name, parent_id: folderId }),
    onSuccess: invalidate,
    onError: (err) =>
      window.alert(err instanceof ApiError ? err.message : "Failed to create folder"),
  });

  const archiveFolder = useMutation({
    mutationFn: (id: string) => api.delete(`/folders/${id}`),
    onSuccess: () => {
      setFolderId(null);
      invalidate();
    },
    onError: (err) =>
      window.alert(err instanceof ApiError ? err.message : "Failed to archive folder"),
  });

  const folders = foldersQuery.data?.data ?? [];
  const assets = assetsQuery.data?.data ?? [];
  const total = assetsQuery.data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Content Library</h1>
        {canCreate && (
          <button
            type="button"
            onClick={() => setUploadOpen(true)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Upload content
          </button>
        )}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[220px_1fr]">
        <aside className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Folders
            </h2>
            {canCreate && (
              <button
                type="button"
                onClick={() => {
                  const name = window.prompt("Folder name");
                  if (name) createFolder.mutate(name);
                }}
                className="text-sm font-medium text-slate-600 hover:underline"
              >
                + New
              </button>
            )}
          </div>
          <ul className="mt-2 space-y-0.5 text-sm">
            <li>
              <button
                type="button"
                onClick={() => {
                  setFolderId(null);
                  setPage(1);
                }}
                className={`w-full rounded-md px-2 py-1.5 text-left ${
                  folderId === null
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                All content
              </button>
            </li>
            {folders.map((folder) => (
              <li key={folder.id} className="group flex items-center">
                <button
                  type="button"
                  onClick={() => {
                    setFolderId(folder.id);
                    setPage(1);
                  }}
                  className={`flex-1 rounded-md px-2 py-1.5 text-left ${
                    folderId === folder.id
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  {folder.name}
                </button>
                {canDelete && (
                  <button
                    type="button"
                    aria-label={`Archive folder ${folder.name}`}
                    onClick={() => {
                      if (window.confirm(`Archive folder "${folder.name}"?`)) {
                        archiveFolder.mutate(folder.id);
                      }
                    }}
                    className="invisible px-1 text-xs text-slate-400 hover:text-red-600 group-hover:visible"
                  >
                    ✕
                  </button>
                )}
              </li>
            ))}
          </ul>
        </aside>

        <div>
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search content…"
              aria-label="Search content"
              className="w-64 rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm"
            />
            <select
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setPage(1);
              }}
              aria-label="Filter by type"
              className="rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm capitalize"
            >
              {TYPE_FILTERS.map((t) => (
                <option key={t} value={t}>
                  {t || "All types"}
                </option>
              ))}
            </select>
          </div>

          {assetsQuery.isLoading ? (
            <Spinner label="Loading content…" />
          ) : assets.length === 0 ? (
            <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
              No content here yet. Upload your first asset to get started.
            </p>
          ) : (
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
              {assets.map((asset) => (
                <button
                  key={asset.id}
                  type="button"
                  onClick={() => setDetailId(asset.id)}
                  className="rounded-lg border border-slate-200 bg-white p-3 text-left transition-shadow hover:shadow-md"
                >
                  <div className="flex h-28 items-center justify-center overflow-hidden rounded-md bg-slate-100">
                    {asset.thumbnail_url ? (
                      <img
                        src={asset.thumbnail_url}
                        alt=""
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <span className="text-2xl uppercase text-slate-400">
                        {asset.type.slice(0, 3)}
                      </span>
                    )}
                  </div>
                  <p className="mt-2 truncate text-sm font-medium text-slate-800">{asset.name}</p>
                  <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                    <StatusBadge status={asset.status} />
                    {asset.current_version && (
                      <span>{formatBytes(asset.current_version.size_bytes)}</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
              <span>
                Page {page} of {totalPages} · {total} assets
              </span>
              <div className="space-x-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {uploadOpen && (
        <UploadModal
          folderId={folderId}
          onClose={() => setUploadOpen(false)}
          onUploaded={invalidate}
        />
      )}
      {detailId && (
        <AssetDetailModal
          assetId={detailId}
          onClose={() => setDetailId(null)}
          onChanged={invalidate}
        />
      )}
    </div>
  );
}
