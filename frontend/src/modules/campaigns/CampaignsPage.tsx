import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { FormField } from "../../components/ui/FormField";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { PlaylistSummary } from "../playlists/types";
import { CampaignDetailModal } from "./CampaignDetailModal";
import { DecisioningTab } from "./DecisioningTab";
import { ExperimentsTab } from "./ExperimentsTab";
import type { CampaignSummary } from "./types";

/** SCR-19 Campaigns (foundation view — targeting/approval arrive in 1I). */
export function CampaignsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("campaigns.manage");
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [tab, setTab] = useState<"campaigns" | "decisioning" | "experiments">("campaigns");

  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get<CampaignSummary[]>("/campaigns?page_size=100"),
  });

  const archive = useMutation({
    mutationFn: (id: string) => api.delete(`/campaigns/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["campaigns"] }),
    onError: (err) => window.alert(err instanceof ApiError ? err.message : "Failed to archive"),
  });

  const campaigns = campaignsQuery.data?.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Campaigns</h1>
        {canManage && (
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            New campaign
          </button>
        )}
      </div>
      <div className="mt-4 border-b border-slate-200" role="tablist">
        {(["campaigns", "decisioning", "experiments"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize ${
              tab === t
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "decisioning" && <DecisioningTab />}
      {tab === "experiments" && <ExperimentsTab />}
      {tab === "campaigns" && (campaignsQuery.isLoading ? (
        <Spinner label="Loading campaigns…" />
      ) : campaigns.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          No campaigns yet.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {campaigns.map((campaign) => (
            <div key={campaign.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between">
                <button
                  type="button"
                  onClick={() => setDetailId(campaign.id)}
                  className="font-medium text-slate-800 hover:underline"
                >
                  {campaign.name}
                </button>
                <StatusBadge status={campaign.status} />
              </div>
              <p className="mt-1 text-sm text-slate-500">
                Priority {campaign.priority} · {campaign.schedule_count} schedule
                {campaign.schedule_count === 1 ? "" : "s"}
              </p>
              <div className="mt-2 flex gap-3">
                <button
                  type="button"
                  onClick={() => setDetailId(campaign.id)}
                  className="text-sm font-medium text-slate-600 hover:underline"
                >
                  Open
                </button>
                {canManage && (
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm(`Archive "${campaign.name}"?`)) {
                        archive.mutate(campaign.id);
                      }
                    }}
                    className="text-sm font-medium text-red-600 hover:underline"
                  >
                    Archive
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      ))}

      {createOpen && (
        <CreateCampaignModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            queryClient.invalidateQueries({ queryKey: ["campaigns"] });
            setCreateOpen(false);
          }}
        />
      )}
      {detailId && (
        <CampaignDetailModal
          campaignId={detailId}
          onClose={() => setDetailId(null)}
          onChanged={() => queryClient.invalidateQueries({ queryKey: ["campaigns"] })}
        />
      )}
    </div>
  );
}

function CreateCampaignModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [priority, setPriority] = useState("50");
  const [playlistId, setPlaylistId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const playlistsQuery = useQuery({
    queryKey: ["playlists"],
    queryFn: () => api.get<PlaylistSummary[]>("/playlists?page_size=100"),
  });

  const create = useMutation({
    mutationFn: () =>
      api.post("/campaigns", {
        name,
        priority: Number(priority) || 50,
        playlist_id: playlistId || null,
      }),
    onSuccess: onCreated,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create campaign"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <Modal title="New campaign" open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <FormField
          id="campaign-name"
          label="Name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <FormField
          id="campaign-priority"
          label="Priority (1-100, higher wins)"
          type="number"
          min={1}
          max={100}
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
        />
        <div>
          <label htmlFor="campaign-playlist" className="block text-sm font-medium text-slate-700">
            Playlist (optional for now)
          </label>
          <select
            id="campaign-playlist"
            value={playlistId}
            onChange={(e) => setPlaylistId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">— none —</option>
            {(playlistsQuery.data?.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
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
            disabled={create.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create campaign"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
