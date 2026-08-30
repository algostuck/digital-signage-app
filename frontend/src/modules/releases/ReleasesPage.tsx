import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo, type DeviceGroup } from "../devices/types";

interface RingDevices {
  total: number;
  pending: number;
  updating: number;
  succeeded: number;
  failed: number;
}

interface Ring {
  id: string;
  ring_no: number;
  percentage: number;
  failure_threshold_pct: number;
  state: string;
  started_at: string | null;
  completed_at: string | null;
  devices: RingDevices;
}

interface Release {
  id: string;
  version: string;
  state: string;
  notes: string | null;
  checksum: string;
  size_bytes: number;
  created_at: string;
  rollout: Ring[];
}

interface RingDeviceRow {
  device_id: string;
  device_name: string;
  state: string;
  failure_reason: string | null;
}

interface UploadSession {
  upload_session_id: string;
  upload_url: string;
  headers: Record<string, string>;
  asset_id: string;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${bytes} B`;
}

/** P2-05 Player Update Center: packages, rollout rings, progress, rollback. */
export function ReleasesPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("releases.manage");
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [rolloutFor, setRolloutFor] = useState<Release | null>(null);

  const releasesQuery = useQuery({
    queryKey: ["player-releases"],
    queryFn: () => api.get<Release[]>("/player-releases"),
    enabled: canManage,
    refetchInterval: 15_000,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["player-releases"] });
  const releases = releasesQuery.data?.data ?? [];

  if (!canManage) {
    return (
      <p className="mt-6 text-sm text-slate-500">
        You need the releases.manage permission to use the Update Center.
      </p>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Player Update Center</h1>
          <p className="mt-1 text-sm text-slate-500">
            Upload player packages and roll them out in staged rings with
            stop-on-failure protection.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
        >
          New release
        </button>
      </div>

      {releasesQuery.isLoading ? (
        <Spinner label="Loading releases…" />
      ) : releases.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No player releases yet. Upload a package to get started.
        </p>
      ) : (
        <ul className="mt-6 space-y-4">
          {releases.map((release) => (
            <ReleaseCard
              key={release.id}
              release={release}
              onStartRollout={() => setRolloutFor(release)}
              onChanged={refresh}
            />
          ))}
        </ul>
      )}

      {showCreate && (
        <CreateReleaseModal onClose={() => setShowCreate(false)} onCreated={refresh} />
      )}
      {rolloutFor && (
        <StartRolloutModal
          release={rolloutFor}
          onClose={() => setRolloutFor(null)}
          onStarted={refresh}
        />
      )}
    </div>
  );
}

function ReleaseCard({
  release,
  onStartRollout,
  onChanged,
}: {
  release: Release;
  onStartRollout: () => void;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const rollback = useMutation({
    mutationFn: () => api.post(`/player-releases/${release.id}/rollback`),
    onSuccess: onChanged,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Rollback failed"),
  });
  const hasRollout = release.rollout.length > 0;

  return (
    <li className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-mono text-sm font-semibold text-slate-900">
          {release.version}
        </span>
        <StatusBadge status={release.state} />
        <span className="text-xs text-slate-500">
          {formatBytes(release.size_bytes)} · created {timeAgo(release.created_at)}
        </span>
        <span className="ml-auto space-x-2">
          {!hasRollout && release.state !== "rolled_back" && (
            <button
              type="button"
              onClick={onStartRollout}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
            >
              Start rollout
            </button>
          )}
          {release.state === "active" && (
            <button
              type="button"
              onClick={() => {
                if (
                  window.confirm(
                    `Roll back ${release.version}? The rollout halts and the update is withdrawn.`,
                  )
                ) {
                  rollback.mutate();
                }
              }}
              className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600"
            >
              Roll back
            </button>
          )}
        </span>
      </div>
      {release.notes && <p className="mt-1 text-sm text-slate-500">{release.notes}</p>}
      {error && (
        <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
      {hasRollout && (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
          {release.rollout.map((ring) => (
            <RingRow key={ring.id} ring={ring} />
          ))}
        </div>
      )}
    </li>
  );
}

function RingRow({ ring }: { ring: Ring }) {
  const [expanded, setExpanded] = useState(false);
  const devicesQuery = useQuery({
    queryKey: ["rollout-ring", ring.id],
    queryFn: () => api.get<RingDeviceRow[]>(`/rollouts/${ring.id}`),
    enabled: expanded,
  });
  const done = ring.devices.succeeded + ring.devices.failed;
  const progressPct = ring.devices.total
    ? Math.round((done / ring.devices.total) * 100)
    : 0;

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full flex-wrap items-center gap-3 text-left"
      >
        <span className="text-sm font-medium text-slate-700">
          Ring {ring.ring_no} · {ring.percentage}%
        </span>
        <StatusBadge status={ring.state} />
        <span className="text-xs text-slate-500">
          {ring.devices.succeeded}/{ring.devices.total} succeeded
          {ring.devices.failed > 0 && (
            <span className="text-red-600"> · {ring.devices.failed} failed</span>
          )}
          {" · "}threshold {ring.failure_threshold_pct}%
        </span>
        <span className="ml-auto h-1.5 w-32 overflow-hidden rounded bg-slate-100">
          <span
            className={`block h-full ${
              ring.state === "stopped" ? "bg-red-500" : "bg-emerald-500"
            }`}
            style={{ width: `${progressPct}%` }}
          />
        </span>
      </button>
      {expanded && (
        <div className="mt-2 rounded-md bg-slate-50 px-3 py-2">
          {devicesQuery.isLoading ? (
            <Spinner label="Loading devices…" />
          ) : (
            <ul className="space-y-1 text-sm text-slate-600">
              {(devicesQuery.data?.data ?? []).map((row) => (
                <li key={row.device_id} className="flex items-center gap-2">
                  <span>{row.device_name}</span>
                  <StatusBadge status={row.state} />
                  {row.failure_reason && (
                    <span className="text-xs text-red-600">{row.failure_reason}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function CreateReleaseModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [version, setVersion] = useState("");
  const [notes, setNotes] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<"idle" | "uploading" | "creating">("idle");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!file || !version.trim()) {
      setError("A version and a package file are required.");
      return;
    }
    setError(null);
    setPhase("uploading");
    try {
      const envelope = await api.post<UploadSession>("/assets/uploads", {
        filename: file.name,
        mime_type: file.type || "application/zip",
        size_bytes: file.size,
        name: `Player package ${version.trim()}`,
      });
      const session = envelope.data!;
      const put = await fetch(session.upload_url, {
        method: "PUT",
        headers: session.headers,
        body: file,
      });
      if (!put.ok) throw new Error(`Package upload failed (${put.status})`);
      await api.post(`/assets/uploads/${session.upload_session_id}/complete`);

      setPhase("creating");
      await api.post("/player-releases", {
        version: version.trim(),
        package_asset_id: session.asset_id,
        notes: notes.trim() || null,
      });
      onCreated();
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Release creation failed",
      );
      setPhase("idle");
    }
  }

  return (
    <Modal title="New player release" open onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label htmlFor="release-version" className="block text-sm font-medium text-slate-700">
            Version
          </label>
          <input
            id="release-version"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
            placeholder="e.g. 2.5.0"
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label htmlFor="release-package" className="block text-sm font-medium text-slate-700">
            Package (.zip)
          </label>
          <input
            id="release-package"
            type="file"
            accept=".zip,application/zip"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm text-slate-600"
          />
        </div>
        <div>
          <label htmlFor="release-notes" className="block text-sm font-medium text-slate-700">
            Notes (optional)
          </label>
          <textarea
            id="release-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
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
            type="button"
            disabled={phase !== "idle"}
            onClick={submit}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {phase === "uploading"
              ? "Uploading…"
              : phase === "creating"
                ? "Creating…"
                : "Create release"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function StartRolloutModal({
  release,
  onClose,
  onStarted,
}: {
  release: Release;
  onClose: () => void;
  onStarted: () => void;
}) {
  const [groupId, setGroupId] = useState("");
  const [rings, setRings] = useState("10, 50, 100");
  const [threshold, setThreshold] = useState("5");
  const [error, setError] = useState<string | null>(null);

  const groupsQuery = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<DeviceGroup[]>("/device-groups"),
  });

  const start = useMutation({
    mutationFn: () => {
      const parsed = rings
        .split(",")
        .map((part) => Number.parseInt(part.trim(), 10))
        .filter((n) => !Number.isNaN(n));
      return api.post(`/player-releases/${release.id}/rollouts`, {
        group_id: groupId || null,
        rings: parsed,
        failure_threshold_pct: Number.parseInt(threshold, 10) || 0,
      });
    },
    onSuccess: () => {
      onStarted();
      onClose();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Rollout failed to start"),
  });

  return (
    <Modal title={`Roll out ${release.version}`} open onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label htmlFor="rollout-group" className="block text-sm font-medium text-slate-700">
            Target
          </label>
          <select
            id="rollout-group"
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="">All active devices</option>
            {(groupsQuery.data?.data ?? []).map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="rollout-rings" className="block text-sm font-medium text-slate-700">
              Rings (cumulative %)
            </label>
            <input
              id="rollout-rings"
              value={rings}
              onChange={(e) => setRings(e.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <p className="mt-1 text-xs text-slate-400">
              Comma-separated, increasing, ending at 100.
            </p>
          </div>
          <div>
            <label htmlFor="rollout-threshold" className="block text-sm font-medium text-slate-700">
              Failure threshold %
            </label>
            <input
              id="rollout-threshold"
              type="number"
              min={0}
              max={100}
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <p className="mt-1 text-xs text-slate-400">
              A ring exceeding this failure share stops the rollout.
            </p>
          </div>
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
            type="button"
            disabled={start.isPending}
            onClick={() => start.mutate()}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {start.isPending ? "Starting…" : "Start rollout"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
