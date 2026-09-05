import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Input,
  List,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  type TableProps,
} from "antd";
import { ToneTag } from "@/design-system";
import { toneOf } from "@/design-system";
import { useState, type FormEvent } from "react";
import { EmptyState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface RuleRow {
  id: string;
  name: string;
  signal_type: string;
  threshold: Record<string, number>;
  window_hours: number;
  severity: string;
  active: boolean;
}

interface AnomalyRow {
  id: string;
  device_id: string;
  score: number;
  state: string;
  evidence: Record<string, unknown>;
  recommendation: string | null;
  opened_at: string | null;
}

const SIGNALS = ["heartbeat_gaps", "playback_failures", "error_events"];
const REMEDIATIONS = ["restart", "clear_cache", "refresh_content"];

const STATE_COLOR: Record<string, string> = {
  open: "error",
  acknowledged: "warning",
  resolved: "success",
};

/** P3-14/15 Fleet Intelligence: deterministic anomaly detection with
 * evidence, human-in-the-loop ack + whitelisted remediation. */
export function IntelligenceTab() {
  const { hasPermission } = useAuth();
  const canRules = hasPermission("settings.manage");
  const canAck = hasPermission("incidents.manage");
  const canRemediate = hasPermission("devices.control");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [ruleForm, setRuleForm] = useState({ name: "", signal_type: "playback_failures" });

  const rulesQuery = useQuery({
    queryKey: ["anomaly-rules"],
    queryFn: () => api.get<RuleRow[]>("/fleet-intelligence/rules"),
    retry: false,
  });
  const anomaliesQuery = useQuery({
    queryKey: ["anomalies"],
    queryFn: () => api.get<AnomalyRow[]>("/fleet-intelligence/anomalies?page_size=50"),
    retry: false,
    refetchInterval: 30000,
  });
  const devicesQuery = useQuery({
    queryKey: ["devices-brief"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/devices?page_size=200"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["anomaly-rules"] });
    queryClient.invalidateQueries({ queryKey: ["anomalies"] });
  };
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const createRule = useMutation({
    mutationFn: () =>
      api.post("/fleet-intelligence/rules", {
        name: ruleForm.name,
        signal_type: ruleForm.signal_type,
      }),
    onSuccess: () => {
      refresh();
      setError(null);
      setRuleForm({ name: "", signal_type: "playback_failures" });
    },
    onError,
  });
  const toggleRule = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.patch(`/fleet-intelligence/rules/${id}`, { active }),
    onSuccess: () => refresh(),
    onError,
  });
  const acknowledge = useMutation({
    mutationFn: (id: string) => api.post(`/fleet-intelligence/${id}/acknowledge`, {}),
    onSuccess: () => refresh(),
    onError,
  });
  const remediate = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api.post(`/fleet-intelligence/${id}/remediation`, { action }),
    onSuccess: () => refresh(),
    onError,
  });

  if (rulesQuery.isError)
    return (
      <Alert
        type="warning"
        showIcon
        role="alert"
        message={
          rulesQuery.error instanceof ApiError
            ? rulesQuery.error.message
            : "Fleet intelligence unavailable."
        }
      />
    );

  const rules = rulesQuery.data?.data ?? [];
  const anomalies = anomaliesQuery.data?.data ?? [];
  const devices = devicesQuery.data?.data ?? [];
  const deviceName = (id: string) => devices.find((d) => d.id === id)?.name ?? id.slice(0, 8);

  function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    createRule.mutate();
  }

  const ruleColumns: TableProps<RuleRow>["columns"] = [
    {
      title: "Rule",
      dataIndex: "name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: "Signal",
      render: (_, rule) => (
        <Typography.Text className="font-mono text-xs">
          {rule.signal_type} · {JSON.stringify(rule.threshold)} · {rule.window_hours}h
        </Typography.Text>
      ),
    },
    {
      title: "Status",
      dataIndex: "active",
      render: (active: boolean) => <StatusBadge status={active ? "active" : "inactive"} />,
    },
    ...(canRules
      ? [
          {
            title: "Actions",
            align: "right" as const,
            render: (_: unknown, rule: RuleRow) => (
              <Button
                size="small"
                onClick={() => toggleRule.mutate({ id: rule.id, active: !rule.active })}
              >
                {rule.active ? "Disable" : "Enable"}
              </Button>
            ),
          },
        ]
      : []),
  ];

  return (
    <Space orientation="vertical" size="middle" className="w-full">
      <Typography.Text type="secondary" className="text-xs">
        Anomalies are explainable statistics over existing telemetry — every
        score shows its evidence, recommendations never auto-execute, and
        remediation is limited to whitelisted, non-destructive commands.
      </Typography.Text>

      <Card
        size="small"
        title="Detection rules"
        extra={
          canRules && (
            <form onSubmit={onCreate}>
              <Space size="small">
                <Input
                  required
                  value={ruleForm.name}
                  onChange={(e) => setRuleForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Rule name"
                  aria-label="Rule name"
                />
                <Select
                  value={ruleForm.signal_type}
                  onChange={(value) => setRuleForm((p) => ({ ...p, signal_type: value }))}
                  aria-label="Signal type"
                  options={SIGNALS.map((s) => ({ value: s, label: s.replace(/_/g, " ") }))}
                  className="w-44"
                />
                <Button type="primary" htmlType="submit" loading={createRule.isPending}>
                  Add rule
                </Button>
              </Space>
            </form>
          )
        }
      >
        <Table<RuleRow>
          size="middle"
          rowKey="id"
          columns={ruleColumns}
          dataSource={rules}
          loading={rulesQuery.isLoading}
          pagination={false}
          scroll={{ x: "max-content" }}
          locale={{
            emptyText: (
              <EmptyState
                title="No detection rules yet"
                description="Anomalies appear once a rule is active (hourly scan)."
              />
            ),
          }}
        />
      </Card>

      <Card size="small" title="Anomalies">
        <List
          dataSource={anomalies}
          loading={anomaliesQuery.isLoading}
          locale={{ emptyText: <EmptyState title="No anomalies detected." /> }}
          renderItem={(a) => (
            <List.Item>
              <Space orientation="vertical" size="small" className="w-full">
                <Space size="small" wrap>
                  <Typography.Text strong>{deviceName(a.device_id)}</Typography.Text>
                  <Tag color={a.score >= 2 ? "error" : "warning"}>score {a.score}</Tag>
                  <ToneTag tone={toneOf(STATE_COLOR[a.state] ?? "default")}>
                    {a.state}
                  </ToneTag>
                </Space>
                <Space size="small" wrap>
                  <Button
                    size="small"
                    onClick={() => setExpanded(expanded === a.id ? null : a.id)}
                  >
                    Evidence
                  </Button>
                  {canAck && a.state === "open" && (
                    <Button size="small" onClick={() => acknowledge.mutate(a.id)}>
                      Acknowledge
                    </Button>
                  )}
                  {canRemediate &&
                    a.state !== "resolved" &&
                    REMEDIATIONS.map((action) => (
                      <Button
                        key={action}
                        size="small"
                        type="primary"
                        onClick={() => remediate.mutate({ id: a.id, action })}
                      >
                        {action.replace(/_/g, " ")}
                      </Button>
                    ))}
                </Space>
                {expanded === a.id && (
                  <Card size="small" type="inner">
                    <Descriptions
                      size="small"
                      column={1}
                      items={[
                        ...(a.recommendation
                          ? [
                              {
                                key: "recommendation",
                                label: "Recommendation",
                                children: a.recommendation,
                              },
                            ]
                          : []),
                        {
                          key: "evidence",
                          label: "Evidence",
                          children: (
                            <Typography.Paragraph className="!mb-0">
                              <pre className="max-h-32 overflow-auto text-xs">
                                {JSON.stringify(a.evidence, null, 2)}
                              </pre>
                            </Typography.Paragraph>
                          ),
                        },
                      ]}
                    />
                  </Card>
                )}
              </Space>
            </List.Item>
          )}
        />
      </Card>

      {error && <Alert type="error" message={error} showIcon role="alert" />}
    </Space>
  );
}
