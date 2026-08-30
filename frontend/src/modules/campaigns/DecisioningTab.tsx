import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
  type TableProps,
} from "antd";
import { useState, type FormEvent } from "react";
import { EmptyState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { CampaignSummary } from "./types";

interface RuleRow {
  id?: string;
  priority: number;
  conditions: Record<string, unknown>;
  actions: Record<string, unknown>;
}

interface PolicyRow {
  id: string;
  name: string;
  guardrails: { mandatory_campaign_ids: string[]; max_switches_per_hour: number };
  active: boolean;
  rules: RuleRow[];
}

interface PreviewResult {
  timezone: string;
  candidates: { id: string; name: string; priority: number; eligible_now: boolean }[];
  scheduler_campaign_id: string | null;
  decided_campaign_id: string | null;
  reasons: Record<string, unknown>[];
}

interface LogRow {
  id: string;
  device_id: string;
  campaign_id: string | null;
  reasons: Record<string, unknown>;
  decided_at: string | null;
}

/** P3-05 Decisioning Rules: deterministic pin/boost/exclude rules with
 * guardrails, a dry-run preview and the auditable decision log. */
export function DecisioningTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("campaigns.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [rulesDraft, setRulesDraft] = useState<string>("");
  const [previewDevice, setPreviewDevice] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [newName, setNewName] = useState("");

  const policiesQuery = useQuery({
    queryKey: ["decision-policies"],
    queryFn: () => api.get<PolicyRow[]>("/decision-policies"),
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get<CampaignSummary[]>("/campaigns?page_size=100"),
  });
  const devicesQuery = useQuery({
    queryKey: ["devices-brief"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/devices?page_size=100"),
  });
  const logQuery = useQuery({
    queryKey: ["decision-log"],
    queryFn: () => api.get<LogRow[]>("/decision-log?page_size=15"),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["decision-policies"] });
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const createPolicy = useMutation({
    mutationFn: () => api.post("/decision-policies", { name: newName }),
    onSuccess: () => {
      refresh();
      setError(null);
      setNewName("");
    },
    onError,
  });
  const toggleActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.patch(`/decision-policies/${id}`, { active }),
    onSuccess: () => refresh(),
    onError,
  });
  const deletePolicy = useMutation({
    mutationFn: (id: string) => api.delete(`/decision-policies/${id}`),
    onSuccess: () => {
      refresh();
      setSelected(null);
    },
    onError,
  });
  const saveRules = useMutation({
    mutationFn: () =>
      api.put(`/decision-policies/${selected}/rules`, { rules: JSON.parse(rulesDraft) }),
    onSuccess: () => {
      refresh();
      setError(null);
    },
    onError,
  });
  const runPreview = useMutation({
    mutationFn: () =>
      api.post<PreviewResult>("/decision-rules/preview", { device_id: previewDevice }),
    onSuccess: (envelope) => {
      setError(null);
      setPreview(envelope.data!);
    },
    onError,
  });

  const policies = policiesQuery.data?.data ?? [];
  const campaigns = campaignsQuery.data?.data ?? [];
  const devices = devicesQuery.data?.data ?? [];
  const logs = logQuery.data?.data ?? [];
  const campaignName = (id: string | null) =>
    campaigns.find((c) => c.id === id)?.name ?? (id ? id.slice(0, 8) : "—");

  function openRules(policy: PolicyRow) {
    setSelected(policy.id);
    setRulesDraft(
      JSON.stringify(
        policy.rules.map(({ priority, conditions, actions }) => ({
          priority,
          conditions,
          actions,
        })),
        null,
        2,
      ) || "[]",
    );
  }

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    createPolicy.mutate();
  }

  const policyColumns: TableProps<PolicyRow>["columns"] = [
    {
      title: "Policy",
      dataIndex: "name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: "Rules",
      render: (_, policy) =>
        `${policy.rules.length} rule${policy.rules.length === 1 ? "" : "s"} · cap ${
          policy.guardrails.max_switches_per_hour
        }/h`,
    },
    {
      title: "Status",
      dataIndex: "active",
      render: (active: boolean) => <StatusBadge status={active ? "active" : "inactive"} />,
    },
    ...(canManage
      ? [
          {
            title: "Actions",
            align: "right" as const,
            render: (_: unknown, policy: PolicyRow) => (
              <Space size="small">
                <Button size="small" onClick={() => openRules(policy)}>
                  Rules
                </Button>
                <Button
                  size="small"
                  onClick={() => toggleActive.mutate({ id: policy.id, active: !policy.active })}
                >
                  {policy.active ? "Deactivate" : "Activate"}
                </Button>
                <Popconfirm
                  title={`Delete policy "${policy.name}"?`}
                  onConfirm={() => deletePolicy.mutate(policy.id)}
                  okButtonProps={{ danger: true }}
                >
                  <Button size="small" danger>
                    Delete
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]
      : []),
  ];

  const logColumns: TableProps<LogRow>["columns"] = [
    {
      title: "When",
      dataIndex: "decided_at",
      render: (decided_at: string | null) =>
        decided_at ? new Date(decided_at).toLocaleString() : "—",
    },
    {
      title: "Campaign",
      dataIndex: "campaign_id",
      render: (campaign_id: string | null) => campaignName(campaign_id),
    },
    {
      title: "Reasons",
      dataIndex: "reasons",
      render: (reasons: Record<string, unknown>) => (
        <Typography.Text
          type="secondary"
          ellipsis
          className="max-w-md font-mono text-xs"
        >
          {JSON.stringify(reasons)}
        </Typography.Text>
      ),
    },
  ];

  return (
    <Space orientation="vertical" size="middle" className="w-full">
      <Typography.Text type="secondary" className="text-xs">
        Rules pin, boost or exclude among the campaigns whose schedule window
        is live right now — schedule windows are never overridden, mandatory
        campaigns are never excluded, and the switch budget prevents
        flapping. Every applied rule is recorded as an auditable reason.
      </Typography.Text>

      <Card
        size="small"
        title="Policies"
        extra={
          canManage && (
            <form onSubmit={onCreate}>
              <Space size="small">
                <Input
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="New policy name"
                  aria-label="New policy name"
                />
                <Button type="primary" htmlType="submit" loading={createPolicy.isPending}>
                  Create
                </Button>
              </Space>
            </form>
          )
        }
      >
        <Table<PolicyRow>
          size="middle"
          rowKey="id"
          columns={policyColumns}
          dataSource={policies}
          loading={policiesQuery.isLoading}
          pagination={false}
          scroll={{ x: "max-content" }}
          locale={{ emptyText: <EmptyState title="No decision policies yet." /> }}
        />

        {selected && canManage && (
          <Card size="small" type="inner" className="mt-3" title="Rules (ordered by priority — JSON)">
            <Typography.Text type="secondary" className="text-xs">
              Conditions: platform, manufacturer, location_id, tag{"{key,value}"},
              time{"{start,end,days}"}, data{"{source_id,path,op,value}"}. Actions:
              one of pin/boost/exclude (campaign id) + optional amount.
            </Typography.Text>
            <Input.TextArea
              value={rulesDraft}
              onChange={(e) => setRulesDraft(e.target.value)}
              rows={10}
              aria-label="Rules JSON"
              className="mt-2 font-mono text-xs"
            />
            <Button
              type="primary"
              className="mt-2"
              loading={saveRules.isPending}
              onClick={() => {
                try {
                  JSON.parse(rulesDraft);
                  setError(null);
                  saveRules.mutate();
                } catch {
                  setError("Rules must be valid JSON");
                }
              }}
            >
              Save rules
            </Button>
          </Card>
        )}
      </Card>

      <Card size="small" title="Preview (dry-run)">
        <Space align="end" wrap>
          <Select
            value={previewDevice || undefined}
            onChange={(value) => setPreviewDevice(value)}
            placeholder="Select device…"
            aria-label="Device"
            showSearch
            optionFilterProp="label"
            options={devices.map((d) => ({ value: d.id, label: d.name }))}
            className="w-64"
          />
          <Button
            type="primary"
            disabled={!previewDevice}
            loading={runPreview.isPending}
            onClick={() => runPreview.mutate()}
          >
            Run preview
          </Button>
        </Space>
        {preview && (
          <div className="mt-3">
            <Typography.Paragraph className="!mb-2">
              Scheduler picks{" "}
              <Typography.Text strong>
                {campaignName(preview.scheduler_campaign_id)}
              </Typography.Text>{" "}
              → decision:{" "}
              <Typography.Text strong>
                {campaignName(preview.decided_campaign_id)}
              </Typography.Text>
            </Typography.Paragraph>
            <Typography.Paragraph className="!mb-0">
              <pre className="max-h-40 overflow-auto text-xs">
                {JSON.stringify(preview.reasons, null, 2)}
              </pre>
            </Typography.Paragraph>
          </div>
        )}
      </Card>

      <Card size="small" title="Decision log">
        <Table<LogRow>
          size="middle"
          rowKey="id"
          columns={logColumns}
          dataSource={logs}
          loading={logQuery.isLoading}
          pagination={false}
          scroll={{ x: "max-content" }}
          locale={{
            emptyText: (
              <EmptyState
                title="No decisions logged"
                description="Log entries record actual switches only."
              />
            ),
          }}
        />
      </Card>

      {error && <Alert type="error" message={error} showIcon role="alert" />}
    </Space>
  );
}
