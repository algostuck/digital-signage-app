import { useState, type FormEvent } from "react";
import { Modal } from "../../components/ui/Modal";
import { api, ApiError } from "../../lib/api";

interface UploadSession {
  upload_session_id: string;
  upload_url: string;
  headers: Record<string, string>;
  asset_id: string;
  version_no: number;
}

interface Props {
  folderId: string | null;
  /** When set, the upload becomes a new version of this asset. */
  assetId?: string;
  onClose: () => void;
  onUploaded: () => void;
}

/** SCR-12 Upload Content: session -> PUT bytes -> complete -> processed. */
export function UploadModal({ folderId, assetId, onClose, onUploaded }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [phase, setPhase] = useState<"idle" | "uploading" | "processing">("idle");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setPhase("uploading");
    try {
      const endpoint = assetId ? `/assets/${assetId}/versions` : "/assets/uploads";
      const envelope = await api.post<UploadSession>(endpoint, {
        filename: file.name,
        mime_type: file.type || "application/octet-stream",
        size_bytes: file.size,
        folder_id: assetId ? undefined : folderId,
        name: assetId ? undefined : name || undefined,
      });
      const session = envelope.data!;

      const put = await fetch(session.upload_url, {
        method: "PUT",
        headers: session.headers,
        body: file,
      });
      if (!put.ok) throw new Error(`Upload failed (${put.status})`);

      setPhase("processing");
      await api.post(`/assets/uploads/${session.upload_session_id}/complete`);
      onUploaded();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : "Upload failed");
      setPhase("idle");
    }
  }

  return (
    <Modal title={assetId ? "Upload new version" : "Upload content"} open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <div>
          <label htmlFor="upload-file" className="block text-sm font-medium text-slate-700">
            File
          </label>
          <input
            id="upload-file"
            type="file"
            required
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white"
          />
        </div>
        {!assetId && (
          <div>
            <label htmlFor="upload-name" className="block text-sm font-medium text-slate-700">
              Display name (defaults to filename)
            </label>
            <input
              id="upload-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm"
            />
          </div>
        )}
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
            disabled={!file || phase !== "idle"}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {phase === "uploading"
              ? "Uploading…"
              : phase === "processing"
                ? "Processing…"
                : "Upload"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
