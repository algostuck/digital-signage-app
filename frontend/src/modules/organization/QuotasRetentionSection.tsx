import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Form, InputNumber, Progress, Row, Space, Typography } from "antd";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface UsageEntry {
  used: number;
  limit: number | null;
}

interface Usage {
  devices: UsageEntry;
  users: UsageEntry;
  storage_mb: UsageEntry;
}

interface RetentionEntry {
  days: number;
  floor: number;
  ceiling: number;
}

/** Usage vs effective limits (read-only — limits come from the plan and
 * Super-Admin quota overrides) + P2-AUD-003 retention policy. */
export function QuotasRetentionSection() {
  const { hasPermission } = useAuth();
  const canSettings = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const usageQuery = useQuery({
    queryKey: ["org-usage"],
    queryFn: () => api.get<Usage>("/organization/usage"),
  });
  const retentionQuery = useQuery({
    queryKey: ["org-retention"],
    queryFn: () => api.get<Record<string, RetentionEntry>>("/organization/retention"),
    enabled: canSettings,
  });

  const [days, setDays] = useState<Record<string, string>>({});
  const usage = usageQuery.data?.data ?? null;
  const retention = retentionQuery.data?.data ?? null;

  useEffect(() => {
    if (retention) {
      setDays(
        Object.fromEntries(
          Object.entries(retention).map(([key, entry]) => [key, String(entry.days)]),
        ),
      );
    }
  }, [retention]);

  const onError = (err: unknown) => {
    setOk(null);
    setError(err instanceof ApiError ? err.message : "Save failed");
  };
  const saveRetention = useMutation({
    mutationFn: () =>
      api.put(
        "/organization/retention",
        Object.fromEntries(Object.entries(days).map(([key, value]) => [key, Number(value)])),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org-retention"] });
      setError(null);
      setOk("Retention policy saved.");
    },
    onError,
  });

  if (!usage) return null;

  const bars: { key: keyof Usage; label: string; unit: string }[] = [
    { key: "devices", label: "Devices", unit: "" },
    { key: "users", label: "Users", unit: "" },
    { key: "storage_mb", label: "Storage", unit: "MB" },
  ];

  return (
    <Space orientation="vertical" size="medium" className="w-full">
      <Card size="small" title="Usage & limits">
        <Typography.Paragraph type="secondary" className="!mb-3">
          Limits come from your subscription plan (and any platform override).
          To change them, upgrade your plan or contact the platform
          administrator.
        </Typography.Paragraph>
        <Row gutter={[16, 16]}>
          {bars.map(({ key, label, unit }) => {
            const entry = usage[key];
            const pct =
              entry.limit != null
                ? Math.min(Math.round((entry.used / entry.limit) * 100), 100)
                : null;
            return (
              <Col key={key} xs={24} sm={8}>
                <Typography.Text>
                  <Typography.Text strong>{label}</Typography.Text>: {entry.used}
                  {unit && ` ${unit}`}
                  {entry.limit != null
                    ? ` of ${entry.limit}${unit ? ` ${unit}` : ""}`
                    : " (no limit)"}
                </Typography.Text>
                <Progress
                  percent={pct ?? 4}
                  showInfo={false}
                  size="small"
                  strokeColor={pct != null && pct >= 90 ? "#EF4444" : "#10B981"}
                />
              </Col>
            );
          })}
        </Row>
      </Card>

      {canSettings && retention && (
        <Card size="small" title="Data retention (days)">
          <Typography.Paragraph type="secondary" className="!mb-3">
            Pruned by the maintenance sweep. Platform floors apply — audit logs
            cannot go below {retention.audit_logs?.floor ?? 90} days.
          </Typography.Paragraph>
          <Form layout="vertical">
            <Row gutter={[12, 0]}>
              {Object.entries(retention).map(([key, entry]) => (
                <Col key={key} xs={12} sm={8}>
                  <Form.Item
                    label={`${key.replace(/_/g, " ")} (${entry.floor}–${entry.ceiling})`}
                    className="!mb-3"
                  >
                    <InputNumber
                      min={entry.floor}
                      max={entry.ceiling}
                      value={days[key] === "" || days[key] == null ? null : Number(days[key])}
                      onChange={(value) =>
                        setDays((prev) => ({
                          ...prev,
                          [key]: value == null ? "" : String(value),
                        }))
                      }
                      className="w-24"
                    />
                  </Form.Item>
                </Col>
              ))}
            </Row>
            <Button
              type="primary"
              loading={saveRetention.isPending}
              onClick={() => saveRetention.mutate()}
            >
              Save retention policy
            </Button>
          </Form>
        </Card>
      )}

      {ok && <Alert type="success" message={ok} showIcon />}
      {error && <Alert type="error" message={error} showIcon role="alert" />}
    </Space>
  );
}
