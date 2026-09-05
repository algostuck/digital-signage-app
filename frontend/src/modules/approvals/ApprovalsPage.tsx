import { CheckOutlined, CloseOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Flex,
  Input,
  List,
  Modal,
  Space,
  Tabs,
  Tag,
  Timeline,
  Typography,
} from "antd";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/design-system";
import { EmptyState, ErrorState, LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo } from "../devices/types";

interface ApprovalAction {
  action: string;
  comments: string | null;
  actor_name: string | null;
  created_at: string;
}

interface ApprovalRequest {
  id: string;
  entity_type: string;
  entity_id: string;
  state: string;
  entity_name: string | null;
  requester_name: string | null;
  submitted_at: string;
  decided_at: string | null;
  comments: string | null;
  actions: ApprovalAction[];
}

const TABS = [
  { key: "pending", label: "Pending" },
  { key: "rejected", label: "Returned" },
  { key: "approved", label: "Approved" },
  { key: "", label: "All" },
] as const;

/** P2-09 Content Approval Inbox. */
export function ApprovalsPage() {
  const { hasPermission } = useAuth();
  const canDecide = hasPermission("campaigns.approve");
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState<string>(searchParams.get("state") ?? "pending");
  const [decision, setDecision] = useState<{
    request: ApprovalRequest;
    approve: boolean;
  } | null>(null);
  const [comments, setComments] = useState("");
  const [error, setError] = useState<string | null>(null);

  const inboxQuery = useQuery({
    queryKey: ["approvals", tab],
    queryFn: () =>
      api.get<ApprovalRequest[]>(`/approvals/inbox?page_size=100${tab ? `&state=${tab}` : ""}`),
    refetchInterval: 30_000,
  });

  const decide = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) =>
      api.post(`/approvals/${id}/${approve ? "approve" : "reject"}`, {
        comments: comments || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["approvals"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      setDecision(null);
      setComments("");
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Decision failed"),
  });

  const rows = inboxQuery.data?.data ?? [];

  const inbox = inboxQuery.isLoading ? (
    <LoadingState rows={4} />
  ) : inboxQuery.isError ? (
    <ErrorState
      title="Unable to load the approval inbox"
      description="You may lack approval permissions."
      onRetry={() => inboxQuery.refetch()}
    />
  ) : rows.length === 0 ? (
    <Card>
      <EmptyState title="Nothing here" description="Submitted items appear in this queue." />
    </Card>
  ) : (
    <List
      dataSource={rows}
      renderItem={(request) => (
        <Card size="small" className="mb-2">
          <Flex wrap align="center" gap="small">
            <Tag className="capitalize">{request.entity_type}</Tag>
            <Typography.Text strong>
              {request.entity_name ?? request.entity_id.slice(0, 8)}
            </Typography.Text>
            <StatusBadge status={request.state} />
            <Typography.Text type="secondary">
              by {request.requester_name ?? "unknown"} · {timeAgo(request.submitted_at)}
            </Typography.Text>
            {request.state === "pending" && canDecide && (
              <Space className="ms-auto">
                <Button
                  type="primary"
                  size="small"
                  icon={<CheckOutlined />}
                  onClick={() => setDecision({ request, approve: true })}
                >
                  Approve
                </Button>
                <Button
                  danger
                  size="small"
                  icon={<CloseOutlined />}
                  onClick={() => setDecision({ request, approve: false })}
                >
                  Reject
                </Button>
              </Space>
            )}
          </Flex>
          {request.actions.length > 1 && (
            <Timeline
              className="!mt-4"
              items={request.actions.map((action) => ({
                children: (
                  <Typography.Text type="secondary" className="text-xs">
                    <span className="font-medium capitalize">{action.action}</span> by{" "}
                    {action.actor_name ?? "system"} · {timeAgo(action.created_at)}
                    {action.comments && <> — “{action.comments}”</>}
                  </Typography.Text>
                ),
              }))}
            />
          )}
        </Card>
      )}
    />
  );

  return (
    <div>
      <PageHeader
        title="Approvals"
        description="Maker-checker governance for campaigns and templates. Configure policies under Settings."
      />

      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={TABS.map((t) => ({ key: t.key, label: t.label, children: inbox }))}
      />

      {decision && (
        <Modal
          title={`${decision.approve ? "Approve" : "Reject"}: ${
            decision.request.entity_name ?? decision.request.entity_type
          }`}
          open
          onCancel={() => setDecision(null)}
          okText={decision.approve ? "Approve" : "Reject"}
          okButtonProps={{ danger: !decision.approve }}
          confirmLoading={decide.isPending}
          onOk={() => decide.mutate({ id: decision.request.id, approve: decision.approve })}
          destroyOnHidden
        >
          {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
          <label htmlFor="decision-comments">
            <Typography.Text>
              Comments {decision.approve ? "(optional)" : "(tell the requester what to fix)"}
            </Typography.Text>
          </label>
          <Input.TextArea
            id="decision-comments"
            className="mt-1"
            value={comments}
            onChange={(e) => setComments(e.target.value)}
            rows={3}
          />
        </Modal>
      )}
    </div>
  );
}
