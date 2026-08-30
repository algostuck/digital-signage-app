import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "../../components/ui/Modal";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { UploadModal } from "./UploadModal";
import { formatBytes, type Asset, type AssetVersion } from "./types";

interface Props {
  assetId: string;
  onClose: () => void;
  onChanged: () => void;
}

/** SCR-13 Content Details: preview, metadata, versions, lifecycle. */
export function AssetDetailModal({ assetId, onClose, onChanged }: Props) {
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("content.edit");
  const canDelete = hasPermission("content.delete");
  const queryClient = useQueryClient();
  const [uploadVersion, setUploadVersion] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const assetQuery = useQuery({
    queryKey: ["asset", assetId],
    queryFn: () => api.get<Asset>(`/assets/${assetId}`),
  });
  const versionsQuery = useQuery({
    queryKey: ["asset-versions", assetId],
    queryFn: () => api.get<AssetVersion[]>(`/assets/${assetId}/versions`),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["asset", assetId] });
    queryClient.invalidateQueries({ queryKey: ["asset-versions", assetId] });
    onChanged();
  };

  const action = useMutation({
    mutationFn: (verb: string) => api.post(`/assets/${assetId}/${verb}`),
    onSuccess: refresh,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Action failed"),
  });

  async function download() {
    setError(null);
    try {
      const envelope = await api.get<{ url: string }>(`/assets/${assetId}/download-url`);
      window.open(envelope.data!.url, "_blank");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Download unavailable");
    }
  }

  const asset = assetQuery.data?.data ?? null;
  if (!asset) {
    return (
      <Modal title="Content details" open onClose={onClose}>
        <p className="text-sm text-slate-500">Loading…</p>
      </Modal>
    );
  }

  const version = asset.current_version;

  return (
    <Modal title={asset.name} open onClose={onClose}>
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <StatusBadge status={asset.status} />
          <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium capitalize text-slate-600">
            {asset.type}
          </span>
          {version && <StatusBadge status={version.processing_status} />}
        </div>

        {asset.thumbnail_url && (
          <img
            src={asset.thumbnail_url}
            alt={`Preview of ${asset.name}`}
            className="max-h-48 rounded-md border border-slate-200 object-contain"
          />
        )}

        {version && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">File</dt>
              <dd className="text-slate-700">{version.original_filename}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Size</dt>
              <dd className="text-slate-700">{formatBytes(version.size_bytes)}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Dimensions</dt>
              <dd className="text-slate-700">
                {version.width && version.height ? `${version.width}×${version.height}` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Version</dt>
              <dd className="text-slate-700">v{version.version_no}</dd>
            </div>
          </dl>
        )}
        {version?.processing_error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            Processing failed: {version.processing_error}
          </p>
        )}

        {asset.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {asset.tags.map((t) => (
              <span
                key={t.id}
                className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
              >
                {t.key}={t.value}
              </span>
            ))}
          </div>
        )}

        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">Versions</h3>
          <ul className="mt-1 space-y-1 text-sm text-slate-600">
            {(versionsQuery.data?.data ?? []).map((v) => (
              <li key={v.id} className="flex items-center gap-2">
                v{v.version_no} · {v.original_filename} · {formatBytes(v.size_bytes)}
                <StatusBadge status={v.processing_status} />
              </li>
            ))}
          </ul>
        </div>

        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}

        <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 pt-4">
          <button
            type="button"
            onClick={download}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
          >
            Download
          </button>
          {canEdit && (
            <button
              type="button"
              onClick={() => setUploadVersion(true)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
            >
              New version
            </button>
          )}
          {canEdit && asset.status === "draft" && (
            <button
              type="button"
              onClick={() => action.mutate("publish")}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white"
            >
              Publish
            </button>
          )}
          {canDelete && asset.status !== "archived" && (
            <button
              type="button"
              onClick={() => {
                if (window.confirm(`Archive "${asset.name}"?`)) action.mutate("archive");
              }}
              className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600"
            >
              Archive
            </button>
          )}
          {canDelete && asset.status === "archived" && (
            <button
              type="button"
              onClick={() => action.mutate("restore")}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
            >
              Restore
            </button>
          )}
        </div>
      </div>

      {uploadVersion && (
        <UploadModal
          folderId={null}
          assetId={assetId}
          onClose={() => setUploadVersion(false)}
          onUploaded={refresh}
        />
      )}
    </Modal>
  );
}
