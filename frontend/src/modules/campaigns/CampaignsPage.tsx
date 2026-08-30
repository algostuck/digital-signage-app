import { DeleteOutlined, PlusOutlined, RocketOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Tabs,
  Typography,
} from "antd";
import { useState } from "react";
import { PageHeader } from "../../components/ui/PageHeader";
import { EmptyState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { PlaylistSummary } from "../playlists/types";
import { CampaignDetailModal } from "./CampaignDetailModal";
import { DecisioningTab } from "./DecisioningTab";
import { ExperimentsTab } from "./ExperimentsTab";
import type { CampaignSummary } from "./types";

/** SCR-19 Campaigns (foundation view — targeting/approval arrive in 1I). */
export function CampaignsPage() {
  const { hasPermission } = useAuth();
  const { message } = App.useApp();
  const canManage = hasPermission("campaigns.manage");
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [tab, setTab] = useState<"campaigns" | "decisioning" | "experiments">("campaigns");

  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get<CampaignSummary[]>("/campaigns?page_size=100"),
  });

  const archive = useMutation({
    mutationFn: (id: string) => api.delete(`/campaigns/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      message.success("Campaign archived");
    },
    onError: (err) =>
      message.error(err instanceof ApiError ? err.message : "Failed to archive"),
  });

  const campaigns = campaignsQuery.data?.data ?? [];

  const campaignsTab = campaignsQuery.isLoading ? (
    <LoadingState rows={5} />
  ) : campaigns.length === 0 ? (
    <Card>
      <EmptyState
        title="No campaigns yet"
        description="Create your first campaign to publish content to your displays."
        action={
          canManage && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              New campaign
            </Button>
          )
        }
      />
    </Card>
  ) : (
    <Row gutter={[12, 12]}>
      {campaigns.map((campaign) => (
        <Col key={campaign.id} xs={24} sm={12} lg={8}>
          <Card
            size="small"
            hoverable
            onClick={() => setDetailId(campaign.id)}
            actions={[
              <Button
                key="open"
                type="link"
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  setDetailId(campaign.id);
                }}
              >
                Open
              </Button>,
              ...(canManage
                ? [
                    <Popconfirm
                      key="archive"
                      title={`Archive "${campaign.name}"?`}
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        archive.mutate(campaign.id);
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okButtonProps={{ danger: true }}
                    >
                      <Button
                        type="link"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => e.stopPropagation()}
                      >
                        Archive
                      </Button>
                    </Popconfirm>,
                  ]
                : []),
            ]}
          >
            <Flex justify="space-between" align="flex-start" gap="small">
              <Typography.Text strong ellipsis>
                <RocketOutlined className="mr-2 text-slate-400" />
                {campaign.name}
              </Typography.Text>
              <StatusBadge status={campaign.status} />
            </Flex>
            <Typography.Paragraph type="secondary" className="!mb-0 !mt-1">
              Priority {campaign.priority} · {campaign.schedule_count} schedule
              {campaign.schedule_count === 1 ? "" : "s"}
            </Typography.Paragraph>
          </Card>
        </Col>
      ))}
    </Row>
  );

  return (
    <div>
      <PageHeader
        title="Campaigns"
        description="Plan, target, approve and publish content campaigns."
        actions={
          canManage &&
          tab === "campaigns" && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              New campaign
            </Button>
          )
        }
      />

      <Tabs
        activeKey={tab}
        onChange={(key) => setTab(key as typeof tab)}
        items={[
          { key: "campaigns", label: "Campaigns", children: campaignsTab },
          { key: "decisioning", label: "Decisioning", children: <DecisioningTab /> },
          { key: "experiments", label: "Experiments", children: <ExperimentsTab /> },
        ]}
      />

      {createOpen && (
        <CreateCampaignModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            queryClient.invalidateQueries({ queryKey: ["campaigns"] });
            setCreateOpen(false);
          }}
        />
      )}
      {detailId && (
        <CampaignDetailModal
          campaignId={detailId}
          onClose={() => setDetailId(null)}
          onChanged={() => queryClient.invalidateQueries({ queryKey: ["campaigns"] })}
        />
      )}
    </div>
  );
}

function CreateCampaignModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form] = Form.useForm<{ name: string; priority: number; playlist_id?: string }>();
  const [error, setError] = useState<string | null>(null);

  const playlistsQuery = useQuery({
    queryKey: ["playlists"],
    queryFn: () => api.get<PlaylistSummary[]>("/playlists?page_size=100"),
  });

  const create = useMutation({
    mutationFn: (values: { name: string; priority: number; playlist_id?: string }) =>
      api.post("/campaigns", {
        name: values.name,
        priority: values.priority || 50,
        playlist_id: values.playlist_id || null,
      }),
    onSuccess: onCreated,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create campaign"),
  });

  return (
    <Modal
      title="New campaign"
      open
      onCancel={onClose}
      okText="Create campaign"
      confirmLoading={create.isPending}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
      <Form
        form={form}
        layout="vertical"
        initialValues={{ priority: 50 }}
        onFinish={(values) => {
          setError(null);
          create.mutate(values);
        }}
      >
        <Form.Item
          name="name"
          label="Name"
          rules={[{ required: true, message: "Give the campaign a name." }]}
        >
          <Input autoFocus />
        </Form.Item>
        <Form.Item name="priority" label="Priority (1-100, higher wins)">
          <InputNumber min={1} max={100} className="w-full" />
        </Form.Item>
        <Form.Item name="playlist_id" label="Playlist (optional for now)">
          <Select
            allowClear
            placeholder="— none —"
            options={(playlistsQuery.data?.data ?? []).map((p) => ({
              value: p.id,
              label: p.name,
            }))}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
