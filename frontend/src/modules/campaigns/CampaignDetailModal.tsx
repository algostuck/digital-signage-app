import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Checkbox,
  Descriptions,
  Divider,
  Drawer,
  Flex,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Steps,
  Tag,
  Typography,
} from "antd";
import { useState } from "react";
import { LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
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

const TARGET_TYPE_OPTIONS = [
  { value: "location", label: "location" },
  { value: "device", label: "device" },
  { value: "group", label: "group" },
  { value: "tag", label: "tag" },
];

/** Approval-stage progression shown at the top of the drawer. */
const STEP_FOR_STATUS: Record<string, number> = {
  draft: 0,
  pending_approval: 1,
  rejected: 1,
  approved: 2,
  published: 3,
  paused: 3,
};

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
      <Drawer title="Campaign" open onClose={onClose} size={640} placement="right">
        <LoadingState rows={6} />
      </Drawer>
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
    <Drawer
      title={campaign.name}
      open
      onClose={onClose}
      width={640}
      placement="right"
      extra={<StatusBadge status={status} />}
      footer={
        <Flex justify="flex-end" wrap gap="small">
          {canManage && status === "draft" && (
            <Button
              onClick={() => transition.mutate("submit-approval")}
              loading={transition.isPending}
            >
              Submit for approval
            </Button>
          )}
          {canApprove && status === "pending_approval" && (
            <>
              <Button
                type="primary"
                onClick={() => transition.mutate("approve")}
                loading={transition.isPending}
              >
                Approve
              </Button>
              <Popconfirm
                title="Reject this campaign?"
                onConfirm={() => transition.mutate("reject")}
                okButtonProps={{ danger: true }}
              >
                <Button danger>Reject</Button>
              </Popconfirm>
            </>
          )}
          {canPublish && (status === "approved" || status === "published") && (
            <Button
              type="primary"
              onClick={() => transition.mutate("publish")}
              loading={transition.isPending}
            >
              {status === "published" ? "Republish" : "Publish"}
            </Button>
          )}
          {canPublish && status === "published" && (
            <Popconfirm
              title="Pause this campaign?"
              onConfirm={() => transition.mutate("pause")}
            >
              <Button>Pause</Button>
            </Popconfirm>
          )}
          {canPublish && status === "paused" && (
            <Button
              type="primary"
              onClick={() => transition.mutate("resume")}
              loading={transition.isPending}
            >
              Resume
            </Button>
          )}
        </Flex>
      }
    >
      <Space orientation="vertical" size="middle" className="w-full">
        {status !== "archived" && (
          <Steps
            size="small"
            current={STEP_FOR_STATUS[status] ?? 0}
            status={status === "rejected" ? "error" : undefined}
            items={[
              { title: "Draft" },
              { title: status === "rejected" ? "Rejected" : "Approval" },
              { title: "Approved" },
              { title: status === "paused" ? "Paused" : "Published" },
            ]}
          />
        )}

        <Descriptions
          size="small"
          column={3}
          items={[
            { key: "priority", label: "Priority", children: campaign.priority },
            {
              key: "schedules",
              label: "Schedules",
              children: `${campaign.schedule_count} schedule${
                campaign.schedule_count === 1 ? "" : "s"
              }`,
            },
            {
              key: "reach",
              label: "Reach",
              children: `${effectiveCount} device${effectiveCount === 1 ? "" : "s"}`,
            },
          ]}
        />

        <div>
          <Divider titlePlacement="start" plain>
            Targets
          </Divider>
          {campaign.targets.length === 0 ? (
            <Typography.Text type="secondary">
              No targets yet — the campaign cannot publish without them.
            </Typography.Text>
          ) : (
            <Space orientation="vertical" size={4} className="w-full">
              {campaign.targets.map((target) => (
                <Flex key={target.id} align="center" gap="small" wrap>
                  <Tag color={target.is_exclusion ? "error" : "default"}>
                    {target.is_exclusion ? "exclude" : "include"} {target.target_type}
                  </Tag>
                  <Typography.Text>{nameFor(target)}</Typography.Text>
                  {target.target_type === "location" && target.include_descendants && (
                    <Typography.Text type="secondary" className="text-xs">
                      + descendants
                    </Typography.Text>
                  )}
                  {canManage && (
                    <Button
                      type="link"
                      size="small"
                      danger
                      onClick={() => removeTarget(target.id)}
                    >
                      remove
                    </Button>
                  )}
                </Flex>
              ))}
            </Space>
          )}
          {canManage && (
            <Flex align="center" gap="small" wrap className="mt-2">
              <Select
                value={targetType}
                onChange={(value) => {
                  setTargetType(value);
                  setTargetId("");
                }}
                aria-label="Target type"
                options={TARGET_TYPE_OPTIONS}
                className="w-28"
              />
              <Select
                value={targetId || undefined}
                onChange={(value) => setTargetId(value)}
                aria-label="Target"
                placeholder="— choose —"
                showSearch
                optionFilterProp="label"
                options={options.map((option) => ({ value: option.id, label: option.label }))}
                className="min-w-44 flex-1"
              />
              {targetType === "location" && (
                <Checkbox
                  checked={descendants}
                  onChange={(e) => setDescendants(e.target.checked)}
                >
                  descendants
                </Checkbox>
              )}
              <Checkbox checked={exclusion} onChange={(e) => setExclusion(e.target.checked)}>
                exclusion
              </Checkbox>
              <Button
                type="primary"
                onClick={addTarget}
                disabled={!targetId}
                loading={saveTargets.isPending}
              >
                Add target
              </Button>
            </Flex>
          )}
        </div>

        <div>
          <Divider titlePlacement="start" plain>
            Variants (audience-specific creative)
          </Divider>
          {(campaign.variants ?? []).length === 0 ? (
            <Typography.Text type="secondary">
              No variants — every device renders the base creative.
            </Typography.Text>
          ) : (
            <Space orientation="vertical" size={4} className="w-full">
              {campaign.variants.map((variant) => (
                <Flex key={variant.id} align="center" gap="small" wrap>
                  <Tag color="purple">variant p{variant.priority}</Tag>
                  <Typography.Text strong>{variant.name}</Typography.Text>
                  <Typography.Text type="secondary" className="text-xs">
                    for{" "}
                    {variant.targets
                      .map((t) => `${t.target_type}: ${nameFor(t)}`)
                      .join(", ")}
                  </Typography.Text>
                  {canManage && (
                    <Button
                      type="link"
                      size="small"
                      danger
                      onClick={() => removeVariant.mutate(variant.id)}
                    >
                      remove
                    </Button>
                  )}
                </Flex>
              ))}
            </Space>
          )}
          {canManage && (
            <Flex align="center" gap="small" wrap className="mt-2">
              <Input
                value={variantName}
                onChange={(e) => setVariantName(e.target.value)}
                placeholder="Variant name"
                aria-label="Variant name"
                className="w-36"
              />
              <Select
                value={variantPlaylist || undefined}
                onChange={(value) => setVariantPlaylist(value)}
                aria-label="Variant playlist"
                placeholder="— playlist —"
                options={(playlistsQuery.data?.data ?? []).map((p) => ({
                  value: p.id,
                  label: p.name,
                }))}
                className="min-w-36"
              />
              <Select
                value={variantTargetType}
                onChange={(value) => {
                  setVariantTargetType(value);
                  setVariantTargetId("");
                }}
                aria-label="Variant target type"
                options={TARGET_TYPE_OPTIONS}
                className="w-28"
              />
              <Select
                value={variantTargetId || undefined}
                onChange={(value) => setVariantTargetId(value)}
                aria-label="Variant target"
                placeholder="— choose —"
                showSearch
                optionFilterProp="label"
                options={optionsFor(variantTargetType).map((option) => ({
                  value: option.id,
                  label: option.label,
                }))}
                className="min-w-36"
              />
              <InputNumber
                min={1}
                max={100}
                value={variantPriority === "" ? null : Number(variantPriority)}
                onChange={(value) => setVariantPriority(value == null ? "" : String(value))}
                aria-label="Variant priority"
                className="w-20"
              />
              <Button
                type="primary"
                onClick={() => addVariant.mutate()}
                disabled={!variantName || !variantPlaylist || !variantTargetId}
                loading={addVariant.isPending}
              >
                Add variant
              </Button>
            </Flex>
          )}
        </div>

        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Space>
    </Drawer>
  );
}
