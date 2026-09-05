import { PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Flex, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Tag, Typography, type TableProps } from "antd";
import { useState } from "react";

import { DataTable } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { CampaignSummary } from "./types";

interface ExperimentRow {
  id: string;
  campaign_id: string;
  name: string;
  status: string;
  start_at: string | null;
  end_at: string | null;
  control_pct: number;
  arms: { variant_id: string; allocation_pct: number }[];
}

interface ResultArm {
  arm: string;
  variant_id: string | null;
  devices: number;
  playback_count: number;
}

interface VariantRow {
  id: string;
  name: string;
}

interface CampaignDetail {
  id: string;
  variants: VariantRow[];
}

/** P3-06 Experiment Manager: A/B arms over campaign variants with stable
 * per-device assignment and per-arm results. */
export function ExperimentsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("campaigns.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ campaign_id: "", name: "", variant_id: "", pct: "50" });
  const [resultsFor, setResultsFor] = useState<string | null>(null);

  const experimentsQuery = useQuery({
    queryKey: ["experiments"],
    queryFn: () => api.get<ExperimentRow[]>("/experiments"),
    retry: false,
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get<CampaignSummary[]>("/campaigns?page_size=100"),
  });
  const campaignDetailQuery = useQuery({
    queryKey: ["campaign-detail", form.campaign_id],
    queryFn: () => api.get<CampaignDetail>(`/campaigns/${form.campaign_id}`),
    enabled: !!form.campaign_id,
  });
  const resultsQuery = useQuery({
    queryKey: ["experiment-results", resultsFor],
    queryFn: () =>
      api.get<{ control_pct: number; arms: ResultArm[] }>(
        `/experiments/${resultsFor}/results`,
      ),
    enabled: resultsFor != null,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["experiments"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const create = useMutation({
    mutationFn: () =>
      api.post("/experiments", {
        campaign_id: form.campaign_id,
        name: form.name,
        arms: [{ variant_id: form.variant_id, allocation_pct: Number(form.pct) }],
      }),
    onSuccess: () => {
      refresh();
      setError(null);
      setForm({ campaign_id: "", name: "", variant_id: "", pct: "50" });
      setCreateOpen(false);
    },
    onError,
  });
  const transition = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "start" | "stop" }) =>
      api.post(`/experiments/${id}/transition`, { action }),
    onSuccess: () => refresh(),
    onError,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/experiments/${id}`),
    onSuccess: () => refresh(),
    onError,
  });

  if (experimentsQuery.isError)
    return (
      <Alert
        type="warning"
        showIcon
        role="alert"
        className="mt-4"
        message={
          experimentsQuery.error instanceof ApiError
            ? experimentsQuery.error.message
            : "Experiments unavailable."
        }
      />
    );

  const experiments = experimentsQuery.data?.data ?? [];
  const campaigns = campaignsQuery.data?.data ?? [];
  const variants = campaignDetailQuery.data?.data?.variants ?? [];
  const campaignName = (id: string) => campaigns.find((c) => c.id === id)?.name ?? id.slice(0, 8);

  function onCreate() {
    setError(null);
    create.mutate();
  }

  const columns: TableProps<ExperimentRow>["columns"] = [
    {
      title: "Experiment",
      dataIndex: "name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: "Campaign",
      dataIndex: "campaign_id",
      render: (campaign_id: string, exp) => (
        <Space size="small">
          {campaignName(campaign_id)}
          <Tag>control {exp.control_pct}%</Tag>
        </Space>
      ),
    },
    {
      title: "Status",
      dataIndex: "status",
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: "Actions",
      align: "right" as const,
      render: (_, exp) => (
        <Space size="small">
          {canManage && exp.status === "draft" && (
            <Button
              size="small"
              type="primary"
              onClick={() => transition.mutate({ id: exp.id, action: "start" })}
            >
              Start
            </Button>
          )}
          {canManage && exp.status === "running" && (
            <Popconfirm
              title="Stop this experiment?"
              description="Every device reverts to the base creative instantly."
              onConfirm={() => transition.mutate({ id: exp.id, action: "stop" })}
            >
              <Button size="small">Stop</Button>
            </Popconfirm>
          )}
          <Button
            size="small"
            onClick={() => setResultsFor(resultsFor === exp.id ? null : exp.id)}
          >
            Results
          </Button>
          {canManage && exp.status !== "running" && (
            <Popconfirm
              title={`Delete experiment "${exp.name}"?`}
              onConfirm={() => remove.mutate(exp.id)}
              okButtonProps={{ danger: true }}
            >
              <Button size="small" danger>
                Delete
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  const resultColumns: TableProps<ResultArm>["columns"] = [
    { title: "Arm", dataIndex: "arm" },
    { title: "Devices", dataIndex: "devices", align: "right" as const },
    { title: "Playbacks", dataIndex: "playback_count", align: "right" as const },
  ];

  return (
    <Space orientation="vertical" size="medium" className="mt-4 w-full">
      <Flex justify="space-between" align="flex-start" gap="middle" wrap>
        <Typography.Text type="secondary" className="text-xs">
          An experiment A/B-tests a campaign's variants: each device lands in a
          stable arm (same device, same arm, always); the remainder plays the
          base creative as control. Stopping reverts every device instantly.
        </Typography.Text>
        {canManage && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            New experiment
          </Button>
        )}
      </Flex>

      <Card size="small" title="Experiments">
        <DataTable<ExperimentRow>
          rowKey="id"
          columns={columns}
          dataSource={experiments}
          loading={experimentsQuery.isLoading}
          pagination={false}
          emptyTitle="No experiments yet."
        />

        {resultsFor && resultsQuery.data?.data && (
          <Card size="small" type="inner" className="mt-3" title="Results by arm">
            <DataTable<ResultArm>
              rowKey="arm"
              columns={resultColumns}
              dataSource={resultsQuery.data.data.arms}
              pagination={false}
            />
          </Card>
        )}
      </Card>

      {error && <Alert type="error" message={error} showIcon role="alert" />}

      {canManage && (
        <Modal
          title="New experiment"
          open={createOpen}
          onCancel={() => setCreateOpen(false)}
          okText="Create experiment"
          confirmLoading={create.isPending}
          okButtonProps={{ disabled: !form.campaign_id || !form.variant_id || !form.name }}
          onOk={onCreate}
          destroyOnHidden
        >
          <Form layout="vertical">
            <Form.Item label="Campaign" required>
              <Select
                value={form.campaign_id || undefined}
                onChange={(value) =>
                  setForm((p) => ({ ...p, campaign_id: value, variant_id: "" }))
                }
                placeholder="Select…"
                aria-label="Campaign"
                showSearch
                optionFilterProp="label"
                options={campaigns.map((c) => ({ value: c.id, label: c.name }))}
              />
            </Form.Item>
            <Form.Item label="Variant (arm B)" required>
              <Select
                value={form.variant_id || undefined}
                onChange={(value) => setForm((p) => ({ ...p, variant_id: value }))}
                placeholder="Select…"
                aria-label="Variant (arm B)"
                options={variants.map((v) => ({ value: v.id, label: v.name }))}
              />
            </Form.Item>
            <Form.Item label="Allocation %">
              <InputNumber
                min={1}
                max={100}
                value={form.pct === "" ? null : Number(form.pct)}
                onChange={(value) =>
                  setForm((p) => ({ ...p, pct: value == null ? "" : String(value) }))
                }
                aria-label="Allocation %"
                className="w-24"
              />
            </Form.Item>
            <Form.Item label="Name" required>
              <Input
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                aria-label="Name"
              />
            </Form.Item>
          </Form>
        </Modal>
      )}
    </Space>
  );
}
