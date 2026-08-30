import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface WallSummary {
  id: string;
  name: string;
  status: string;
  canvas: { width: number; height: number; rows: number; cols: number };
  members: number;
}

interface WallMemberState {
  member_id: string;
  device_id: string;
  device_name: string | null;
  viewport: { x: number; y: number; width: number; height: number };
  role: string;
  online: boolean;
}

interface WallState {
  id: string;
  name: string;
  status: string;
  canvas: { width: number; height: number; rows: number; cols: number };
  sync_policy: { tolerance_ms: number };
  session: { id: string; started_at: string | null; start_epoch_ms: number | null } | null;
  members: WallMemberState[];
}

const STATUS_STYLE: Record<string, string> = {
  idle: "bg-slate-100 text-slate-600",
  syncing: "bg-emerald-100 text-emerald-700",
  degraded: "bg-amber-100 text-amber-800",
  archived: "bg-slate-100 text-slate-400",
};

/** P3-07/08 Video Wall Manager + Control: shared canvas, member viewports,
 * sync sessions with degraded-state honesty. */
export function WallsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("devices.manage");
  const canControl = hasPermission("devices.control");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [wallForm, setWallForm] = useState({ name: "", cols: "2", rows: "1" });
  const [memberForm, setMemberForm] = useState({ device_id: "", cell: "0" });

  const wallsQuery = useQuery({
    queryKey: ["video-walls"],
    queryFn: () => api.get<WallSummary[]>("/video-walls"),
    retry: false,
  });
  const wallQuery = useQuery({
    queryKey: ["video-wall", selected],
    queryFn: () => api.get<WallState>(`/video-walls/${selected}`),
    enabled: selected != null,
    refetchInterval: 15000,
  });
  const devicesQuery = useQuery({
    queryKey: ["devices-brief"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/devices?page_size=100"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["video-walls"] });
    queryClient.invalidateQueries({ queryKey: ["video-wall", selected] });
  };
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const createWall = useMutation({
    mutationFn: () => {
      const cols = Number(wallForm.cols) || 1;
      const rows = Number(wallForm.rows) || 1;
      return api.post("/video-walls", {
        name: wallForm.name,
        canvas: { width: 1920 * cols, height: 1080 * rows, rows, cols },
      });
    },
    onSuccess: () => {
      refresh();
      setError(null);
      setWallForm({ name: "", cols: "2", rows: "1" });
    },
    onError,
  });
  const deleteWall = useMutation({
    mutationFn: (id: string) => api.delete(`/video-walls/${id}`),
    onSuccess: () => {
      refresh();
      setSelected(null);
    },
    onError,
  });
  const addMember = useMutation({
    mutationFn: () => {
      const wall = wallQuery.data?.data;
      if (!wall) throw new Error("no wall");
      const cell = Number(memberForm.cell);
      const col = cell % wall.canvas.cols;
      const row = Math.floor(cell / wall.canvas.cols);
      const width = wall.canvas.width / wall.canvas.cols;
      const height = wall.canvas.height / wall.canvas.rows;
      return api.post(`/video-walls/${selected}/members`, {
        device_id: memberForm.device_id,
        viewport: { x: col * width, y: row * height, width, height },
        role: wall.members.length === 0 ? "leader" : "member",
      });
    },
    onSuccess: () => {
      refresh();
      setError(null);
    },
    onError,
  });
  const removeMember = useMutation({
    mutationFn: (memberId: string) =>
      api.delete(`/video-walls/${selected}/members/${memberId}`),
    onSuccess: () => refresh(),
    onError,
  });
  const syncAction = useMutation({
    mutationFn: (action: "start" | "stop") =>
      api.post(`/video-walls/${selected}/sync`, { action }),
    onSuccess: () => refresh(),
    onError,
  });

  if (wallsQuery.isError)
    return (
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
        {wallsQuery.error instanceof ApiError
          ? wallsQuery.error.message
          : "Video walls unavailable."}
      </p>
    );

  const walls = wallsQuery.data?.data ?? [];
  const wall = wallQuery.data?.data ?? null;
  const devices = devicesQuery.data?.data ?? [];
  const cellCount = wall ? wall.canvas.rows * wall.canvas.cols : 0;

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    createWall.mutate();
  }

  return (
    <div className="space-y-6">
      {canManage && (
        <form
          className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
          onSubmit={onCreate}
        >
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Wall name</span>
            <input
              required
              value={wallForm.name}
              onChange={(e) => setWallForm((p) => ({ ...p, name: e.target.value }))}
              className="mt-0.5 w-52 rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Columns</span>
            <input
              type="number"
              min={1}
              max={8}
              value={wallForm.cols}
              onChange={(e) => setWallForm((p) => ({ ...p, cols: e.target.value }))}
              className="mt-0.5 w-20 rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Rows</span>
            <input
              type="number"
              min={1}
              max={8}
              value={wallForm.rows}
              onChange={(e) => setWallForm((p) => ({ ...p, rows: e.target.value }))}
              className="mt-0.5 w-20 rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <button
            type="submit"
            disabled={createWall.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Create wall (1080p per cell)
          </button>
        </form>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Video walls
        </h2>
        <table className="mt-2 w-full text-left text-sm">
          <tbody>
            {walls.length === 0 && (
              <tr>
                <td className="py-3 text-sm text-slate-400">No walls yet.</td>
              </tr>
            )}
            {walls.map((w) => (
              <tr key={w.id} className="border-t border-slate-100">
                <td className="py-2 pr-4 font-medium text-slate-800">{w.name}</td>
                <td className="py-2 pr-4 text-xs text-slate-500">
                  {w.canvas.cols}×{w.canvas.rows} · {w.canvas.width}×{w.canvas.height}px ·{" "}
                  {w.members} member{w.members === 1 ? "" : "s"}
                </td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      STATUS_STYLE[w.status] ?? ""
                    }`}
                  >
                    {w.status}
                  </span>
                </td>
                <td className="py-2">
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => setSelected(selected === w.id ? null : w.id)}
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600"
                    >
                      {selected === w.id ? "Close" : "Manage"}
                    </button>
                    {canManage && (
                      <button
                        type="button"
                        onClick={() => deleteWall.mutate(w.id)}
                        className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium text-red-600"
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {wall && selected && (
          <div className="mt-3 space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
            {wall.status === "degraded" && (
              <p className="rounded-md bg-amber-100 px-3 py-2 text-sm text-amber-800">
                Wall degraded — one or more members are offline. Healthy members
                keep playing standalone; sync resumes when they return.
              </p>
            )}
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase text-slate-400">
                Members — {wall.name}
                {wall.session && (
                  <span className="ml-2 font-mono normal-case text-slate-500">
                    session {wall.session.id.slice(0, 8)} · tolerance{" "}
                    {wall.sync_policy.tolerance_ms}ms
                  </span>
                )}
              </h3>
              {canControl && (
                <button
                  type="button"
                  disabled={syncAction.isPending}
                  onClick={() =>
                    syncAction.mutate(wall.session ? "stop" : "start")
                  }
                  className={`rounded-md px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 ${
                    wall.session ? "bg-amber-600" : "bg-emerald-600"
                  }`}
                >
                  {wall.session ? "Stop sync" : "Start sync"}
                </button>
              )}
            </div>
            <table className="w-full text-left text-sm">
              <tbody>
                {wall.members.map((m) => (
                  <tr key={m.member_id} className="border-t border-slate-200">
                    <td className="py-1.5 pr-4">{m.device_name}</td>
                    <td className="py-1.5 pr-4 font-mono text-xs">
                      {m.viewport.x},{m.viewport.y} {m.viewport.width}×{m.viewport.height}
                    </td>
                    <td className="py-1.5 pr-4 text-xs">{m.role}</td>
                    <td className="py-1.5 pr-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          m.online
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {m.online ? "online" : "offline"}
                      </span>
                    </td>
                    {canManage && (
                      <td className="py-1.5">
                        <button
                          type="button"
                          onClick={() => removeMember.mutate(m.member_id)}
                          className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium text-red-600"
                        >
                          Remove
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            {canManage && (
              <div className="flex items-end gap-2">
                <label className="block text-sm">
                  <span className="block text-xs text-slate-500">Device</span>
                  <select
                    value={memberForm.device_id}
                    onChange={(e) =>
                      setMemberForm((p) => ({ ...p, device_id: e.target.value }))
                    }
                    className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
                  >
                    <option value="">Select…</option>
                    {devices.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="block text-xs text-slate-500">Cell (0-based)</span>
                  <select
                    value={memberForm.cell}
                    onChange={(e) => setMemberForm((p) => ({ ...p, cell: e.target.value }))}
                    className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
                  >
                    {Array.from({ length: cellCount }, (_, i) => (
                      <option key={i} value={i}>
                        {i}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  disabled={!memberForm.device_id || addMember.isPending}
                  onClick={() => addMember.mutate()}
                  className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
                >
                  Add member
                </button>
              </div>
            )}
          </div>
        )}
      </section>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
