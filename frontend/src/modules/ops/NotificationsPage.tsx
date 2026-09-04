import { CheckOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Badge,
  Button,
  Card,
  Checkbox,
  Flex,
  List,
  Select,
  Space,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader } from "../../components/ui/PageHeader";
import { EmptyState, LoadingState } from "../../components/ui/states";
import { api } from "../../lib/api";
import { timeAgo } from "../devices/types";
import { NotificationRulesTab } from "./NotificationRulesTab";

interface NotificationRow {
  id: string;
  type: string;
  severity: string;
  title: string;
  message: string | null;
  read_at: string | null;
  created_at: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  info: "processing",
  warning: "warning",
  critical: "error",
};

/** SCR-25 Notifications inbox + P2-18 rules. */
export function NotificationsPage() {
  const [tab, setTab] = useState<"inbox" | "rules">("inbox");

  return (
    <div>
      <PageHeader
        title="Notifications"
        description="In-app alerts and the rules that route them to email, webhooks and escalations."
      />
      <Tabs
        activeKey={tab}
        onChange={(key) => setTab(key as typeof tab)}
        items={[
          { key: "inbox", label: "Inbox", children: <InboxTab /> },
          { key: "rules", label: "Rules", children: <NotificationRulesTab /> },
        ]}
      />
    </div>
  );
}

function InboxTab() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [severity, setSeverity] = useState(searchParams.get("severity") ?? "");
  const [unreadOnly, setUnreadOnly] = useState(searchParams.get("unread") === "1");
  const inboxQuery = useQuery({
    queryKey: ["notifications", unreadOnly],
    queryFn: () =>
      api.get<NotificationRow[]>(
        `/notifications?page_size=100${unreadOnly ? "&unread_only=true" : ""}`,
      ),
    refetchInterval: 30_000,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
    queryClient.invalidateQueries({ queryKey: ["monitoring-summary"] });
  };
  const markRead = useMutation({
    mutationFn: (id: string) => api.post(`/notifications/${id}/read`),
    onSuccess: refresh,
  });
  const markAll = useMutation({
    mutationFn: () => api.post("/notifications/read-all"),
    onSuccess: refresh,
  });

  const rows = (inboxQuery.data?.data ?? []).filter((r) => !severity || r.severity === severity);
  const unread = rows.filter((r) => !r.read_at).length;

  return (
    <div>
      <Flex justify="space-between" align="center" wrap gap="small" className="mb-3">
        <Space wrap>
          <Select
            className="w-40"
            value={severity}
            aria-label="Filter by severity"
            onChange={setSeverity}
            options={[
              { value: "", label: "All severities" },
              { value: "critical", label: "Critical" },
              { value: "warning", label: "Warning" },
              { value: "info", label: "Info" },
            ]}
          />
          <Checkbox checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)}>
            Unread only
          </Checkbox>
        </Space>
        {unread > 0 && (
          <Button
            icon={<CheckOutlined />}
            loading={markAll.isPending}
            onClick={() => markAll.mutate()}
          >
            Mark all read ({unread})
          </Button>
        )}
      </Flex>

      {inboxQuery.isLoading ? (
        <LoadingState rows={4} />
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            title="No notifications"
            description="Device registrations, approval requests and deployment failures appear here."
          />
        </Card>
      ) : (
        <List
          dataSource={rows}
          renderItem={(row) => (
            <Card key={row.id} size="small" className={`mb-2 ${row.read_at ? "opacity-60" : ""}`}>
              <Flex wrap align="center" gap="small">
                <Tag color={SEVERITY_COLORS[row.severity] ?? "default"} variant="filled">
                  {row.severity}
                </Tag>
                <div className="min-w-0 flex-1">
                  <Typography.Text strong={!row.read_at}>
                    {!row.read_at && <Badge status="processing" className="mr-2" />}
                    {row.title}
                  </Typography.Text>
                  {row.message && (
                    <Typography.Paragraph type="secondary" className="!mb-0">
                      {row.message}
                    </Typography.Paragraph>
                  )}
                </div>
                <Typography.Text type="secondary" className="text-xs">
                  {timeAgo(row.created_at)}
                </Typography.Text>
                {!row.read_at && (
                  <Button type="link" size="small" onClick={() => markRead.mutate(row.id)}>
                    Mark read
                  </Button>
                )}
              </Flex>
            </Card>
          )}
        />
      )}
    </div>
  );
}
