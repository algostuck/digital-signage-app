import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "../../components/ui/Modal";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Device, DeviceGroup } from "../devices/types";
import type { LocationNode, LocationTag } from "../locations/types";
import type { CampaignDetail } from "./types";

interface Props {
  campaignId: string;
  onClose: () => void;
  onChanged: () => void;
}

/** SCR-20 Campaign Editor: targeting, approval workflow, publish. */
export function CampaignDetailModal({ campaignId, onClose, onChanged }: Props) {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("campaigns.manage");
  const canApprove = hasPermission("campaigns.approve");
  const canPublish = hasPermission("campaigns.publish");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [targetType, setTargetType] = useState<"location" | "device" | "group" | "tag">("location");
  const [targetId, setTargetId] = useState("");
  const [descendants, setDescendants] = useState(true);
  const [exclusion, setExclusion] = useState(false);

  const campaignQuery = useQuery({
    queryKey: ["campaign", campaignId],
    queryFn: () => api.get<CampaignDetail>(`/campaigns/${campaignId}`),
  });
  const effectiveQuery = useQuery({
    queryKey: ["campaign-effective", campaignId],
    queryFn: () =>
      api.get<{ id: string; name: string }[]>(`/campaigns/${campaignId}/effective-targets`),
  });
  const locationsQuery = useQuery({
    queryKey: ["locations-flat"],
    queryFn: () => api.get<LocationNode[]>("/locations?page_size=200"),
    enabled: canManage,
  });
  const devicesQuery = useQuery({
    queryKey: ["devices-flat"],
    queryFn: () => api.get<Device[]>("/devices?page_size=200&status=active"),
    enabled: canManage,
  });
  const groupsQuery = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<DeviceGroup[]>("/device-groups"),
    enabled: canManage,
  });
  const tagsQuery = useQuery({
    queryKey: ["tags"],
    queryFn: () => api.get<LocationTag[]>("/tags"),
    enabled: canManage,
  });
  const playlistsQuery = useQuery({
    queryKey: ["playlists-published"],
    queryFn: () =>
      api.get<{ id: string; name: string }[]>("/playlists?status=published&page_size=100"),
    enabled: canManage,
  });

  // Variant form state (P2-CAM-001).
  const [variantName, setVariantName] = useState("");
  const [variantPlaylist, setVariantPlaylist] = useState("");
  const [variantPriority, setVariantPriority] = useState("60");
  const [variantTargetType, setVariantTargetType] = useState<
    "location" | "device" | "group" | "tag"
  >("location");
  const [variantTargetId, setVariantTargetId] = useState("");

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
    queryClient.invalidateQueries({ queryKey: ["campaign-effective", campaignId] });
    queryClient.invalidateQueries({ queryKey: ["campaigns"] });
    queryClient.invalidateQueries({ queryKey: ["deployments"] });
    onChanged();
  };
  const onErr = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const transition = useMutation({
    mutationFn: (verb: string) => api.post(`/campaigns/${campaignId}/${verb}`),
    onSuccess: () => {
      setError(null);
      refresh();
    },
    onError: onErr,
  });
  const addVariant = useMutation({
    mutationFn: () =>
      api.post(`/campaigns/${campaignId}/variants`, {
        name: variantName,
        playlist_id: variantPlaylist,
        priority: Number(variantPriority) || 60,
        targets: [
          {
            target_type: variantTargetType,
            target_id: variantTargetId,
            include_descendants: true,
          },
        ],
      }),
    onSuccess: () => {
      setError(null);
      setVariantName("");
      setVariantTargetId("");
      refresh();
    },
    onError: onErr,
  });
  const removeVariant = useMutation({
    mutationFn: (variantId: string) =>
      api.delete(`/campaigns/${campaignId}/variants/${variantId}`),
    onSuccess: refresh,
    onError: onErr,
  });
  const saveTargets = useMutation({
    mutationFn: (
      targets: {
        target_type: string;
        target_id: string;
        include_descendants: boolean;
        is_exclusion: boolean;
      }[],
    ) => api.post(`/campaigns/${campaignId}/targets`, { targets }),
    onSuccess: () => {
      setError(null);
      setTargetId("");
      refresh();
    },
    onError: onErr,
  });

  const campaign = campaignQuery.data?.data ?? null;
  if (!campaign) {
    return (
      <Modal title="Campaign" open onClose={onClose}>
        <p className="text-sm text-slate-500">Loading…</p>
      </Modal>
    );
  }

  const nameFor = (target: { target_type: string; target_id: string }): string => {
    const pools: Record<string, { id: string; label: string }[]> = {
      location: (locationsQuery.data?.data ?? []).map((l) => ({ id: l.id, label: l.name })),
      device: (devicesQuery.data?.data ?? []).map((d) => ({ id: d.id, label: d.name })),
      group: (groupsQuery.data?.data ?? []).map((g) => ({ id: g.id, label: g.name })),
      tag: (tagsQuery.data?.data ?? []).map((t) => ({ id: t.id, label: `${t.key}=${t.value}` })),
    };
    return (
      pools[target.target_type]?.find((entry) => entry.id === target.target_id)?.label ??
      target.target_id.slice(0, 8)
    );
  };

  const optionsFor = (
    type: "location" | "device" | "group" | "tag",
  ): { id: string; label: string }[] =>
    type === "location"
      ? (locationsQuery.data?.data ?? []).map((l) => ({ id: l.id, label: l.name }))
      : type === "device"
        ? (devicesQuery.data?.data ?? []).map((d) => ({ id: d.id, label: d.name }))
        : type === "group"
          ? (groupsQuery.data?.data ?? []).map((g) => ({ id: g.id, label: g.name }))
          : (tagsQuery.data?.data ?? []).map((t) => ({ id: t.id, label: `${t.key}=${t.value}` }));
  const options = optionsFor(targetType);

  function addTarget() {
    if (!targetId || !campaign) return;
    saveTargets.mutate([
      ...campaign.targets.map((t) => ({
        target_type: t.target_type,
        target_id: t.target_id,
        include_descendants: t.include_descendants,
        is_exclusion: t.is_exclusion,
      })),
      {
        target_type: targetType,
        target_id: targetId,
        include_descendants: descendants,
        is_exclusion: exclusion,
      },
    ]);
  }

  function removeTarget(id: string) {
    if (!campaign) return;
    saveTargets.mutate(
      campaign.targets
        .filter((t) => t.id !== id)
        .map((t) => ({
          target_type: t.target_type,
          target_id: t.target_id,
          include_descendants: t.include_descendants,
          is_exclusion: t.is_exclusion,
        })),
    );
  }

  const status = campaign.status;
  const effectiveCount = effectiveQuery.data?.data?.length ?? 0;

  return (
    <Modal title={campaign.name} open onClose={onClose}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={status} />
          <span className="text-sm text-slate-500">
            Priority {campaign.priority} · {campaign.schedule_count} schedule
            {campaign.schedule_count === 1 ? "" : "s"} · reaches {effectiveCount} device
            {effectiveCount === 1 ? "" : "s"}
          </span>
        </div>

        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">Targets</h3>
          {campaign.targets.length === 0 ? (
            <p className="mt-1 text-sm text-slate-500">
              No targets yet — the campaign cannot publish without them.
            </p>
          ) : (
            <ul className="mt-1 space-y-1 text-sm">
              {campaign.targets.map((target) => (
                <li key={target.id} className="flex items-center gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                      target.is_exclusion
                        ? "bg-red-50 text-red-700"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {target.is_exclusion ? "exclude" : "include"} {target.target_type}
                  </span>
                  <span className="text-slate-700">{nameFor(target)}</span>
                  {target.target_type === "location" && target.include_descendants && (
                    <span className="text-xs text-slate-400">+ descendants</span>
                  )}
                  {canManage && (
                    <button
                      type="button"
                      onClick={() => removeTarget(target.id)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      remove
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {canManage && (
            <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-slate-200 p-2 text-sm">
              <select
                value={targetType}
                onChange={(e) => {
                  setTargetType(e.target.value as typeof targetType);
                  setTargetId("");
                }}
                aria-label="Target type"
                className="rounded-md border border-slate-300 px-2 py-1"
              >
                <option value="location">location</option>
                <option value="device">device</option>
                <option value="group">group</option>
                <option value="tag">tag</option>
              </select>
              <select
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                aria-label="Target"
                className="min-w-40 rounded-md border border-slate-300 px-2 py-1"
              >
                <option value="">— choose —</option>
                {options.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
              {targetType === "location" && (
                <label className="flex items-center gap-1 text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={descendants}
                    onChange={(e) => setDescendants(e.target.checked)}
                  />
                  descendants
                </label>
              )}
              <label className="flex items-center gap-1 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={exclusion}
                  onChange={(e) => setExclusion(e.target.checked)}
                />
                exclusion
              </label>
              <button
                type="button"
                onClick={addTarget}
                disabled={!targetId || saveTargets.isPending}
                className="rounded-md bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
              >
                Add target
              </button>
            </div>
          )}
        </div>

        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
            Variants (audience-specific creative)
          </h3>
          {(campaign.variants ?? []).length === 0 ? (
            <p className="mt-1 text-sm text-slate-500">
              No variants — every device renders the base creative.
            </p>
          ) : (
            <ul className="mt-1 space-y-1 text-sm">
              {campaign.variants.map((variant) => (
                <li key={variant.id} className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-xs font-medium text-indigo-700">
                    variant p{variant.priority}
                  </span>
                  <span className="font-medium text-slate-700">{variant.name}</span>
                  <span className="text-xs text-slate-500">
                    for{" "}
                    {variant.targets
                      .map((t) => `${t.target_type}: ${nameFor(t)}`)
                      .join(", ")}
                  </span>
                  {canManage && (
                    <button
                      type="button"
                      onClick={() => removeVariant.mutate(variant.id)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      remove
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {canManage && (
            <div className="mt-2 flex flex-wrap items-center gap-2 rounded-md border border-slate-200 p-2 text-sm">
              <input
                value={variantName}
                onChange={(e) => setVariantName(e.target.value)}
                placeholder="Variant name"
                aria-label="Variant name"
                className="w-32 rounded-md border border-slate-300 px-2 py-1"
              />
              <select
                value={variantPlaylist}
                onChange={(e) => setVariantPlaylist(e.target.value)}
                aria-label="Variant playlist"
                className="rounded-md border border-slate-300 px-2 py-1"
              >
                <option value="">— playlist —</option>
                {(playlistsQuery.data?.data ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <select
                value={variantTargetType}
                onChange={(e) => {
                  setVariantTargetType(e.target.value as typeof variantTargetType);
                  setVariantTargetId("");
                }}
                aria-label="Variant target type"
                className="rounded-md border border-slate-300 px-2 py-1"
              >
                <option value="location">location</option>
                <option value="device">device</option>
                <option value="group">group</option>
                <option value="tag">tag</option>
              </select>
              <select
                value={variantTargetId}
                onChange={(e) => setVariantTargetId(e.target.value)}
                aria-label="Variant target"
                className="min-w-32 rounded-md border border-slate-300 px-2 py-1"
              >
                <option value="">— choose —</option>
                {optionsFor(variantTargetType).map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
              <input
                type="number"
                min={1}
                max={100}
                value={variantPriority}
                onChange={(e) => setVariantPriority(e.target.value)}
                aria-label="Variant priority"
                className="w-16 rounded-md border border-slate-300 px-2 py-1"
              />
              <button
                type="button"
                onClick={() => addVariant.mutate()}
                disabled={
                  !variantName || !variantPlaylist || !variantTargetId || addVariant.isPending
                }
                className="rounded-md bg-slate-900 px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
              >
                Add variant
              </button>
            </div>
          )}
        </div>

        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}

        <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 pt-4">
          {canManage && status === "draft" && (
            <ActionButton onClick={() => transition.mutate("submit-approval")}>
              Submit for approval
            </ActionButton>
          )}
          {canApprove && status === "pending_approval" && (
            <>
              <ActionButton onClick={() => transition.mutate("approve")} tone="primary">
                Approve
              </ActionButton>
              <ActionButton onClick={() => transition.mutate("reject")} tone="danger">
                Reject
              </ActionButton>
            </>
          )}
          {canPublish && (status === "approved" || status === "published") && (
            <ActionButton onClick={() => transition.mutate("publish")} tone="primary">
              {status === "published" ? "Republish" : "Publish"}
            </ActionButton>
          )}
          {canPublish && status === "published" && (
            <ActionButton onClick={() => transition.mutate("pause")}>Pause</ActionButton>
          )}
          {canPublish && status === "paused" && (
            <ActionButton onClick={() => transition.mutate("resume")} tone="primary">
              Resume
            </ActionButton>
          )}
        </div>
      </div>
    </Modal>
  );
}

function ActionButton({
  onClick,
  children,
  tone = "neutral",
}: {
  onClick: () => void;
  children: React.ReactNode;
  tone?: "neutral" | "primary" | "danger";
}) {
  const cls =
    tone === "primary"
      ? "bg-emerald-600 text-white"
      : tone === "danger"
        ? "border border-red-200 text-red-600"
        : "border border-slate-300 text-slate-600";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium ${cls}`}
    >
      {children}
    </button>
  );
}
