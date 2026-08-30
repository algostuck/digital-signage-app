import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  CloudUploadOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Checkbox,
  Flex,
  Form,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Radio,
  Select,
  Space,
  Tag,
  Typography,
} from "antd";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { PageHeader } from "../../components/ui/PageHeader";
import { EmptyState, LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Asset } from "../content/types";
import type { LayoutSummary } from "../design/types";
import { formatDuration, type PlaylistDetail, type PlaylistItem, type PlaylistSummary } from "./types";

const TRANSITIONS = ["none", "fade", "slide"];

/** SCR-18 Playlist Editor: sequencing, duration, transition, fallback. */
export function PlaylistEditorPage() {
  const { playlistId } = useParams<{ playlistId: string }>();
  const { hasPermission } = useAuth();
  const canManage = hasPermission("playlists.manage");
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const playlistQuery = useQuery({
    queryKey: ["playlist", playlistId],
    queryFn: () => api.get<PlaylistDetail>(`/playlists/${playlistId}`),
  });
  const fallbackOptionsQuery = useQuery({
    queryKey: ["playlists"],
    queryFn: () => api.get<PlaylistSummary[]>("/playlists?page_size=100"),
    enabled: canManage,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["playlist", playlistId] });
    queryClient.invalidateQueries({ queryKey: ["playlists"] });
  };
  const onError = (err: unknown) =>
    setMessage({ kind: "error", text: err instanceof ApiError ? err.message : "Action failed" });

  const patchPlaylist = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch(`/playlists/${playlistId}`, body),
    onSuccess: refresh,
    onError,
  });
  const patchItem = useMutation({
    mutationFn: ({ itemId, body }: { itemId: string; body: Record<string, unknown> }) =>
      api.patch(`/playlists/${playlistId}/items/${itemId}`, body),
    onSuccess: refresh,
    onError,
  });
  const removeItem = useMutation({
    mutationFn: (itemId: string) => api.delete(`/playlists/${playlistId}/items/${itemId}`),
    onSuccess: refresh,
    onError,
  });
  const publish = useMutation({
    mutationFn: () => api.post(`/playlists/${playlistId}/publish`),
    onSuccess: () => {
      refresh();
      setMessage({ kind: "ok", text: "Playlist published." });
    },
    onError,
  });

  const playlist = playlistQuery.data?.data ?? null;
  if (!playlist) return <LoadingState rows={6} />;

  const fallbackOptions = (fallbackOptionsQuery.data?.data ?? []).filter(
    (p) => p.id !== playlist.id,
  );

  return (
    <div>
      <PageHeader
        title={playlist.name}
        breadcrumbs={[{ label: "Playlists", to: "/playlists" }, { label: playlist.name }]}
        description={`${playlist.items.length} items · ${formatDuration(
          playlist.total_duration_ms,
        )} total`}
        actions={
          canManage && (
            <>
              <Button icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>
                Add item
              </Button>
              <Button
                type="primary"
                icon={<CloudUploadOutlined />}
                onClick={() => publish.mutate()}
                loading={publish.isPending}
              >
                Publish
              </Button>
            </>
          )
        }
      />

      <Space size="small" wrap>
        <StatusBadge status={playlist.status} />
        {playlist.current_version_no && <Tag>v{playlist.current_version_no}</Tag>}
      </Space>

      {message && (
        <Alert
          className="mt-2"
          type={message.kind === "ok" ? "success" : "error"}
          message={message.text}
          showIcon
          role="alert"
        />
      )}

      {canManage && (
        <Card size="small" className="mt-3">
          <Space size="large" wrap>
            <Checkbox
              checked={playlist.loop_enabled}
              onChange={(e) => patchPlaylist.mutate({ loop_enabled: e.target.checked })}
            >
              Loop playback
            </Checkbox>
            <Space size="small">
              <Typography.Text type="secondary">Fallback:</Typography.Text>
              <Select
                value={playlist.fallback_playlist_id ?? ""}
                aria-label="Fallback playlist"
                onChange={(value) =>
                  patchPlaylist.mutate(
                    value ? { fallback_playlist_id: value } : { clear_fallback: true },
                  )
                }
                options={[
                  { value: "", label: "none" },
                  ...fallbackOptions.map((p) => ({ value: p.id, label: p.name })),
                ]}
                className="min-w-44"
              />
            </Space>
          </Space>
        </Card>
      )}

      {playlist.items.length === 0 ? (
        <Card className="mt-4">
          <EmptyState
            title="No items yet"
            description="Add published content or layouts to build the sequence."
          />
        </Card>
      ) : (
        <List
          className="mt-4"
          dataSource={playlist.items}
          renderItem={(item, index) => (
            <ItemRow
              key={item.id}
              item={item}
              index={index}
              total={playlist.items.length}
              canManage={canManage}
              onMove={(pos) => patchItem.mutate({ itemId: item.id, body: { position: pos } })}
              onDuration={(ms) =>
                patchItem.mutate({ itemId: item.id, body: { duration_ms: ms } })
              }
              onTransition={(t) =>
                patchItem.mutate({
                  itemId: item.id,
                  body: { transition: t === "none" ? {} : { type: t } },
                })
              }
              onToggle={(enabled) => patchItem.mutate({ itemId: item.id, body: { enabled } })}
              onRemove={() => removeItem.mutate(item.id)}
            />
          )}
        />
      )}

      {addOpen && (
        <AddItemModal
          playlistId={playlist.id}
          onClose={() => setAddOpen(false)}
          onAdded={() => {
            refresh();
            setAddOpen(false);
          }}
        />
      )}
    </div>
  );
}

function ItemRow({
  item,
  index,
  total,
  canManage,
  onMove,
  onDuration,
  onTransition,
  onToggle,
  onRemove,
}: {
  item: PlaylistItem;
  index: number;
  total: number;
  canManage: boolean;
  onMove: (position: number) => void;
  onDuration: (ms: number) => void;
  onTransition: (transition: string) => void;
  onToggle: (enabled: boolean) => void;
  onRemove: () => void;
}) {
  const [duration, setDuration] = useState<number | null>(
    item.duration_ms != null ? item.duration_ms / 1000 : null,
  );

  return (
    <List.Item className={item.enabled ? undefined : "opacity-50"}>
      <Flex align="center" gap="middle" wrap className="w-full">
        <Typography.Text strong type="secondary" className="w-6 text-center">
          {item.position}
        </Typography.Text>
        <Avatar
          shape="square"
          size={48}
          src={item.thumbnail_url ?? undefined}
          alt=""
          className="shrink-0"
        >
          {item.item_type === "layout" ? "layout" : item.asset_type ?? "?"}
        </Avatar>
        <div className="min-w-0 flex-1">
          <Typography.Text strong ellipsis className="block">
            {item.name}
          </Typography.Text>
          <Space size="small">
            <Typography.Text type="secondary" className="text-xs">
              {item.item_type}
            </Typography.Text>
            {!item.ready && (
              <Typography.Text type="danger" className="text-xs">
                not ready
              </Typography.Text>
            )}
          </Space>
        </div>
        {canManage ? (
          <Space size="small" wrap>
            <InputNumber
              min={1}
              value={duration}
              onChange={(value) => setDuration(value)}
              onBlur={() => {
                const seconds = Number(duration);
                if (seconds > 0 && seconds * 1000 !== item.duration_ms) {
                  onDuration(Math.round(seconds * 1000));
                }
              }}
              addonAfter="sec"
              aria-label={`Duration for ${item.name}`}
              className="w-28"
            />
            <Select
              value={item.transition_json?.type ?? "none"}
              onChange={(value) => onTransition(value)}
              aria-label={`Transition for ${item.name}`}
              options={TRANSITIONS.map((t) => ({ value: t, label: t }))}
              className="w-24"
            />
            <Button
              size="small"
              icon={<ArrowUpOutlined />}
              disabled={index === 0}
              onClick={() => onMove(item.position - 1)}
              aria-label={`Move ${item.name} up`}
            />
            <Button
              size="small"
              icon={<ArrowDownOutlined />}
              disabled={index === total - 1}
              onClick={() => onMove(item.position + 1)}
              aria-label={`Move ${item.name} down`}
            />
            <Button size="small" onClick={() => onToggle(!item.enabled)}>
              {item.enabled ? "Disable" : "Enable"}
            </Button>
            <Popconfirm
              title={`Remove "${item.name}" from the playlist?`}
              onConfirm={onRemove}
              okButtonProps={{ danger: true }}
            >
              <Button size="small" danger>
                Remove
              </Button>
            </Popconfirm>
          </Space>
        ) : (
          <Typography.Text type="secondary">
            {item.duration_ms != null ? formatDuration(item.duration_ms) : "natural"}
          </Typography.Text>
        )}
      </Flex>
    </List.Item>
  );
}

function AddItemModal({
  playlistId,
  onClose,
  onAdded,
}: {
  playlistId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [form] = Form.useForm<{ refId: string; seconds: number | null }>();
  const [kind, setKind] = useState<"asset" | "layout">("asset");
  const [error, setError] = useState<string | null>(null);

  const assetsQuery = useQuery({
    queryKey: ["assets-for-playlist"],
    queryFn: () => api.get<Asset[]>("/assets?page_size=100"),
  });
  const layoutsQuery = useQuery({
    queryKey: ["layouts-for-playlist"],
    queryFn: () => api.get<LayoutSummary[]>("/layouts?status=published&page_size=100"),
  });

  const readyAssets = (assetsQuery.data?.data ?? []).filter(
    (a) => a.current_version?.processing_status === "ready",
  );
  const layouts = layoutsQuery.data?.data ?? [];

  const add = useMutation({
    mutationFn: (values: { refId: string; seconds: number | null }) =>
      api.post(`/playlists/${playlistId}/items`, {
        asset_id: kind === "asset" ? values.refId : undefined,
        layout_id: kind === "layout" ? values.refId : undefined,
        duration_ms:
          Number(values.seconds) > 0 ? Math.round(Number(values.seconds) * 1000) : undefined,
      }),
    onSuccess: onAdded,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to add item"),
  });

  const options = kind === "asset" ? readyAssets : layouts;

  return (
    <Modal
      title="Add playlist item"
      open
      onCancel={onClose}
      okText="Add item"
      confirmLoading={add.isPending}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon role="alert" className="mb-4" />}
      <Form
        form={form}
        layout="vertical"
        initialValues={{ seconds: 8 }}
        onFinish={(values) => {
          setError(null);
          add.mutate(values);
        }}
      >
        <Form.Item label="Item kind">
          <Radio.Group
            value={kind}
            optionType="button"
            buttonStyle="solid"
            aria-label="Item kind"
            onChange={(e) => {
              setKind(e.target.value);
              form.setFieldsValue({ refId: undefined });
            }}
            options={[
              { value: "asset", label: "Asset" },
              { value: "layout", label: "Layout" },
            ]}
          />
        </Form.Item>
        <Form.Item
          name="refId"
          label={kind === "asset" ? "Content (READY only)" : "Layout (published only)"}
          rules={[{ required: true, message: "Choose an item to add" }]}
        >
          <Select
            placeholder="— choose —"
            showSearch
            optionFilterProp="label"
            options={options.map((o) => ({ value: o.id, label: o.name }))}
          />
        </Form.Item>
        <Form.Item name="seconds" label="Duration (seconds)">
          <InputNumber min={1} className="w-32" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
