import { CloseOutlined, RedoOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  Col,
  Flex,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader } from "../../components/ui/PageHeader";
import { EmptyState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../devices/types";
import type { DeploymentDeviceRow, DeploymentSummary } from "./types";

/** SCR-22 Publishing / Deployments: jobs, progress, retry, target status. */
export function DeploymentsPage() {
  const { hasPermission } = useAuth();
  const { message } = App.useApp();
  const canManage = hasPermission("deployments.manage");
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [searchParams] = useSearchParams();
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") ?? "");

  const deploymentsQuery = useQuery({
    queryKey: ["deployments", statusFilter],
    queryFn: () =>
      api.get<DeploymentSummary[]>(
        `/deployments?page_size=100${statusFilter ? `&status=${statusFilter}` : ""}`,
      ),
    refetchInterval: 15_000,
  });
  const devicesQuery = useQuery({
    queryKey: ["deployment-devices", expanded],
    queryFn: () => api.get<DeploymentDeviceRow[]>(`/deployments/${expanded}/devices`),
    enabled: expanded != null,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["deployments"] });
    queryClient.invalidateQueries({ queryKey: ["deployment-devices"] });
  };

  const action = useMutation({
    mutationFn: ({ id, verb }: { id: string; verb: string }) =>
      api.post(`/deployments/${id}/${verb}`),
    onSuccess: refresh,
    onError: (err) => message.error(err instanceof ApiError ? err.message : "Action failed"),
  });

  const deployments = deploymentsQuery.data?.data ?? [];

  return (
    <div>
      <PageHeader
        title="Publishing"
        description="Deployment jobs with per-device delivery status. Players acknowledge after syncing."
        actions={
          <Select
            className="w-44"
            value={statusFilter}
            aria-label="Filter by status"
            onChange={setStatusFilter}
            options={[
              { value: "", label: "All statuses" },
              ...["queued", "publishing", "partial", "published", "failed", "cancelled"].map((s) => ({
                value: s,
                label: s.charAt(0).toUpperCase() + s.slice(1),
              })),
            ]}
          />
        }
      />

      {deploymentsQuery.isLoading ? (
        <LoadingState rows={5} />
      ) : deployments.length === 0 ? (
        <Card>
          <EmptyState
            title="No deployments yet"
            description="Publish an approved campaign to create one."
          />
        </Card>
      ) : (
        <Space orientation="vertical" size="small" className="w-full">
          {deployments.map((deployment) => {
            const done = deployment.acknowledged;
            const total = deployment.total_devices || 1;
            const percent = Math.round((done / total) * 100);
            return (
              <Card key={deployment.id} size="small">
                <Flex wrap align="center" gap="middle">
                  <div className="min-w-0 flex-1">
                    <Space size="small">
                      <Typography.Text strong>{deployment.campaign_name}</Typography.Text>
                      <Typography.Text type="secondary">
                        v{deployment.version} · {timeAgo(deployment.created_at)}
                      </Typography.Text>
                    </Space>
                    <Flex align="center" gap="middle" className="mt-1">
                      <Progress
                        percent={percent}
                        size="small"
                        className="max-w-56"
                        status={
                          deployment.failed > 0
                            ? "exception"
                            : percent === 100
                              ? "success"
                              : "active"
                        }
                      />
                      <Typography.Text type="secondary" className="text-xs">
                        {deployment.acknowledged}/{deployment.total_devices} acknowledged
                        {deployment.pending > 0 && ` · ${deployment.pending} pending`}
                      </Typography.Text>
                      {deployment.failed > 0 && (
                        <Tag color="error" variant="filled">
                          {deployment.failed} failed
                        </Tag>
                      )}
                    </Flex>
                  </div>
                  <StatusBadge status={deployment.status} />
                  <Button
                    type="link"
                    size="small"
                    onClick={() => setExpanded(expanded === deployment.id ? null : deployment.id)}
                  >
                    {expanded === deployment.id ? "Hide devices" : "Devices"}
                  </Button>
                  {canManage && deployment.failed > 0 && deployment.status !== "cancelled" && (
                    <Button
                      size="small"
                      icon={<RedoOutlined />}
                      onClick={() => action.mutate({ id: deployment.id, verb: "retry" })}
                    >
                      Retry failed
                    </Button>
                  )}
                  {canManage && !["published", "cancelled"].includes(deployment.status) && (
                    <Popconfirm
                      title="Cancel this deployment?"
                      onConfirm={() => action.mutate({ id: deployment.id, verb: "cancel" })}
                      okButtonProps={{ danger: true }}
                    >
                      <Button size="small" danger icon={<CloseOutlined />}>
                        Cancel
                      </Button>
                    </Popconfirm>
                  )}
                </Flex>

                {expanded === deployment.id &&
                  (devicesQuery.isLoading ? (
                    <LoadingState rows={2} />
                  ) : (
                    <Row gutter={[8, 8]} className="mt-3">
                      {(devicesQuery.data?.data ?? []).map((row) => (
                        <Col key={row.device_id} xs={24} sm={12} lg={8}>
                          <Card size="small" styles={{ body: { padding: "6px 10px" } }}>
                            <Space size="small" className="w-full">
                              <StatusBadge status={row.status} />
                              <Typography.Text ellipsis>{row.device_name}</Typography.Text>
                              {row.last_error && (
                                <Typography.Text
                                  type="danger"
                                  ellipsis
                                  className="text-xs"
                                  title={row.last_error}
                                >
                                  {row.last_error}
                                </Typography.Text>
                              )}
                            </Space>
                          </Card>
                        </Col>
                      ))}
                    </Row>
                  ))}
              </Card>
            );
          })}
        </Space>
      )}
    </div>
  );
}
