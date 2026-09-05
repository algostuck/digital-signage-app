import { PlaySquareOutlined, PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Flex, Form, Input, Modal, Row, Typography } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../../components/ui/PageHeader";
import { EmptyState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDuration, type PlaylistDetail, type PlaylistSummary } from "./types";

/** SCR-17 Playlists. */
export function PlaylistsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("playlists.manage");
  const navigate = useNavigate();
  const [createOpen, setCreateOpen] = useState(false);

  const playlistsQuery = useQuery({
    queryKey: ["playlists"],
    queryFn: () => api.get<PlaylistSummary[]>("/playlists?page_size=100"),
  });

  const playlists = playlistsQuery.data?.data ?? [];

  return (
    <div>
      <PageHeader
        title="Playlists"
        description="Ordered sequences of content and layouts, versioned for publishing."
        actions={
          canManage && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              New playlist
            </Button>
          )
        }
      />

      {playlistsQuery.isLoading ? (
        <LoadingState rows={5} />
      ) : playlists.length === 0 ? (
        <Card>
          <EmptyState
            title="No playlists yet"
            description="A playlist is an ordered sequence of content or layouts."
            action={
              canManage && (
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => setCreateOpen(true)}
                >
                  New playlist
                </Button>
              )
            }
          />
        </Card>
      ) : (
        <Row gutter={[12, 12]}>
          {playlists.map((playlist) => (
            <Col key={playlist.id} xs={24} sm={12} lg={8}>
              <Card
                size="small"
                hoverable
                onClick={() => navigate(`/playlists/${playlist.id}`)}
                tabIndex={0}
                role="button"
                aria-label={`Open playlist ${playlist.name}`}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") navigate(`/playlists/${playlist.id}`);
                }}
              >
                <Flex justify="space-between" align="flex-start" gap="small">
                  <Typography.Text strong ellipsis>
                    <PlaySquareOutlined className="mr-2 text-slate-600 dark:text-slate-400" />
                    {playlist.name}
                  </Typography.Text>
                  <StatusBadge status={playlist.status} />
                </Flex>
                <Typography.Paragraph type="secondary" className="!mb-0 !mt-1">
                  {playlist.item_count} item{playlist.item_count === 1 ? "" : "s"} ·{" "}
                  {formatDuration(playlist.total_duration_ms)}
                  {playlist.loop_enabled ? " · loops" : ""}
                  {playlist.current_version_no ? ` · v${playlist.current_version_no}` : ""}
                </Typography.Paragraph>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {createOpen && (
        <CreatePlaylistModal
          onClose={() => setCreateOpen(false)}
          onCreated={(id) => navigate(`/playlists/${id}`)}
        />
      )}
    </div>
  );
}

function CreatePlaylistModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<{ name: string }>();
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (values: { name: string }) =>
      api.post<PlaylistDetail>("/playlists", { name: values.name }),
    onSuccess: (envelope) => {
      queryClient.invalidateQueries({ queryKey: ["playlists"] });
      onCreated(envelope.data!.id);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create playlist"),
  });

  return (
    <Modal
      title="New playlist"
      open
      onCancel={onClose}
      okText="Create & open editor"
      confirmLoading={create.isPending}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => {
          setError(null);
          create.mutate(values);
        }}
      >
        <Form.Item
          name="name"
          label="Name"
          rules={[{ required: true, message: "Give the playlist a name." }]}
        >
          <Input autoFocus />
        </Form.Item>
      </Form>
    </Modal>
  );
}
