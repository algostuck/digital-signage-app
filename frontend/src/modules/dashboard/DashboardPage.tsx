import {
  BellOutlined,
  CloudUploadOutlined,
  DesktopOutlined,
  FolderOutlined,
  RocketOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Badge, Button, Card, Col, List, Row, Tag, Typography } from "antd";
import { Link, useNavigate } from "react-router-dom";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatCard } from "../../components/ui/StatCard";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api } from "../../lib/api";
import { GOLDEN_SPLIT } from "../../theme/tokens";
import { timeAgo } from "../devices/types";

interface Summary {
  devices: { total: number; online: number; warning: number; offline: number; pending: number };
  content: { total: number; published: number; draft: number };
  campaigns: { published: number; pending_approval: number; approved: number; draft: number };
  deployments: { publishing: number; partial: number; published: number; failed: number };
  notifications_unread: number;
  recent_deployments: {
    id: string;
    campaign_name: string;
    version: number;
    status: string;
    total_devices: number;
    acknowledged: number;
    failed: number;
    created_at: string;
  }[];
  recent_activity: {
    id: string;
    action: string;
    entity_type: string;
    user_name: string | null;
    created_at: string;
  }[];
}

/** SCR-02 Dashboard: all critical health information at a glance. */
export function DashboardPage() {
  const navigate = useNavigate();
  const summaryQuery = useQuery({
    queryKey: ["monitoring-summary"],
    queryFn: () => api.get<Summary>("/monitoring/summary"),
    refetchInterval: 30_000,
  });

  if (summaryQuery.isLoading) return <LoadingState rows={8} />;
  const data = summaryQuery.data?.data;
  if (!data) {
    return (
      <ErrorState
        title="Unable to load the dashboard"
        description="The monitoring service did not respond."
        onRetry={() => summaryQuery.refetch()}
      />
    );
  }

  const deploymentsInProgress = data.deployments.publishing + data.deployments.partial;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Platform health at a glance — devices, content, campaigns and publishing."
        actions={
          data.notifications_unread > 0 && (
            <Badge count={data.notifications_unread} overflowCount={99}>
              <Button icon={<BellOutlined />} onClick={() => navigate("/notifications")}>
                Notifications
              </Button>
            </Badge>
          )
        }
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <Link to="/devices">
            <StatCard
              label="Devices online"
              icon={<DesktopOutlined />}
              value={`${data.devices.online}/${data.devices.total}`}
              valueColor={data.devices.offline > 0 ? "#D97706" : "#059669"}
              context={`${data.devices.warning} warning · ${data.devices.offline} offline${
                data.devices.pending ? ` · ${data.devices.pending} pending approval` : ""
              }`}
            />
          </Link>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Link to="/content">
            <StatCard
              label="Content"
              icon={<FolderOutlined />}
              value={data.content.total}
              context={`${data.content.published} published · ${data.content.draft} draft`}
            />
          </Link>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Link to="/campaigns">
            <StatCard
              label="Active campaigns"
              icon={<RocketOutlined />}
              value={data.campaigns.published}
              valueColor={data.campaigns.pending_approval > 0 ? "#D97706" : undefined}
              context={`${data.campaigns.pending_approval} awaiting approval · ${data.campaigns.draft} draft`}
            />
          </Link>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Link to="/deployments">
            <StatCard
              label="Deployments"
              icon={<CloudUploadOutlined />}
              value={deploymentsInProgress + data.deployments.published}
              valueColor={data.deployments.failed > 0 ? "#DC2626" : undefined}
              context={`${deploymentsInProgress} in progress · ${data.deployments.failed} failed`}
            />
          </Link>
        </Col>
      </Row>

      <Row gutter={[16, 16]} className="mt-4">
        <Col xs={24} xl={GOLDEN_SPLIT.primary}>
          <Card
            title="Recent deployments"
            size="small"
            extra={<Link to="/deployments">View all</Link>}
          >
            {data.recent_deployments.length === 0 ? (
              <EmptyState
                title="Nothing published yet"
                description="Publish a campaign to see its rollout here."
              />
            ) : (
              <List
                dataSource={data.recent_deployments}
                renderItem={(deployment) => (
                  <List.Item className="!px-0">
                    <div className="flex w-full flex-wrap items-center gap-3">
                      <StatusBadge status={deployment.status} />
                      <Typography.Text strong>{deployment.campaign_name}</Typography.Text>
                      <Typography.Text type="secondary">
                        v{deployment.version} · {deployment.acknowledged}/
                        {deployment.total_devices} acked
                      </Typography.Text>
                      {deployment.failed > 0 && (
                        <Tag color="error" variant="filled">
                          {deployment.failed} failed
                        </Tag>
                      )}
                      <Typography.Text type="secondary" className="ml-auto text-xs">
                        {timeAgo(deployment.created_at)}
                      </Typography.Text>
                    </div>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} xl={GOLDEN_SPLIT.secondary}>
          <Card title="Recent activity" size="small" extra={<Link to="/audit">Audit log</Link>}>
            {data.recent_activity.length === 0 ? (
              <EmptyState title="No activity recorded yet" />
            ) : (
              <List
                dataSource={data.recent_activity}
                renderItem={(entry) => (
                  <List.Item className="!px-0 !py-2">
                    <div className="flex w-full items-center gap-2">
                      <Typography.Text code className="text-xs">
                        {entry.action}
                      </Typography.Text>
                      <Typography.Text type="secondary" className="truncate text-sm">
                        {entry.user_name ?? "system"}
                      </Typography.Text>
                      <Typography.Text type="secondary" className="ml-auto shrink-0 text-xs">
                        {timeAgo(entry.created_at)}
                      </Typography.Text>
                    </div>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
