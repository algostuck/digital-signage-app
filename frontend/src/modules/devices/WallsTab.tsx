import {
  CaretRightOutlined,
  DeleteOutlined,
  PlusOutlined,
  StopOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Flex,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Table,
  Typography,
  type TableProps,
} from "antd";
import { useState } from "react";
import { EmptyState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface WallSummary {
  id: string;
  name: string;
  status: string;
  canvas: { width: number; height: number; rows: number; cols: number };
  members: number;
}

interface WallMemberState {
  member_id: string;
  device_id: string;
  device_name: string | null;
  viewport: { x: number; y: number; width: number; height: number };
  role: string;
  online: boolean;
}

interface WallState {
  id: string;
  name: string;
  status: string;
  canvas: { width: number; height: number; rows: number; cols: number };
  sync_policy: { tolerance_ms: number };
  session: { id: string; started_at: string | null; start_epoch_ms: number | null } | null;
  members: WallMemberState[];
}

interface WallFormValues {
  name: string;
  cols: number;
  rows: number;
}

/** P3-07/08 Video Wall Manager + Control: shared canvas, member viewports,
 * sync sessions with degraded-state honesty. */
export function WallsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("devices.manage");
  const canControl = hasPermission("devices.control");
  const queryClient = useQueryClient();
  const [form] = Form.useForm<WallFormValues>();
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [memberForm, setMemberForm] = useState({ device_id: "", cell: "0" });

  const wallsQuery = useQuery({
    queryKey: ["video-walls"],
    queryFn: () => api.get<WallSummary[]>("/video-walls"),
    retry: false,
  });
  const wallQuery = useQuery({
    queryKey: ["video-wall", selected],
    queryFn: () => api.get<WallState>(`/video-walls/${selected}`),
    enabled: selected != null,
    refetchInterval: 15000,
  });
  const devicesQuery = useQuery({
    queryKey: ["devices-brief"],
    queryFn: () => api.get<{ id: string; name: string }[]>("/devices?page_size=100"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["video-walls"] });
    queryClient.invalidateQueries({ queryKey: ["video-wall", selected] });
  };
  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const createWall = useMutation({
    mutationFn: (values: WallFormValues) => {
      const cols = Number(values.cols) || 1;
      const rows = Number(values.rows) || 1;
      return api.post("/video-walls", {
        name: values.name,
        canvas: { width: 1920 * cols, height: 1080 * rows, rows, cols },
      });
    },
    onSuccess: () => {
      refresh();
      setError(null);
      form.resetFields();
    },
    onError,
  });
  const deleteWall = useMutation({
    mutationFn: (id: string) => api.delete(`/video-walls/${id}`),
    onSuccess: () => {
      refresh();
      setSelected(null);
    },
    onError,
  });
  const addMember = useMutation({
    mutationFn: () => {
      const wall = wallQuery.data?.data;
      if (!wall) throw new Error("no wall");
      const cell = Number(memberForm.cell);
      const col = cell % wall.canvas.cols;
      const row = Math.floor(cell / wall.canvas.cols);
      const width = wall.canvas.width / wall.canvas.cols;
      const height = wall.canvas.height / wall.canvas.rows;
      return api.post(`/video-walls/${selected}/members`, {
        device_id: memberForm.device_id,
        viewport: { x: col * width, y: row * height, width, height },
        role: wall.members.length === 0 ? "leader" : "member",
      });
    },
    onSuccess: () => {
      refresh();
      setError(null);
    },
    onError,
  });
  const removeMember = useMutation({
    mutationFn: (memberId: string) =>
      api.delete(`/video-walls/${selected}/members/${memberId}`),
    onSuccess: () => refresh(),
    onError,
  });
  const syncAction = useMutation({
    mutationFn: (action: "start" | "stop") =>
      api.post(`/video-walls/${selected}/sync`, { action }),
    onSuccess: () => refresh(),
    onError,
  });

  if (wallsQuery.isError)
    return (
      <Alert
        type="warning"
        showIcon
        role="alert"
        message={
          wallsQuery.error instanceof ApiError
            ? wallsQuery.error.message
            : "Video walls unavailable."
        }
      />
    );

  const walls = wallsQuery.data?.data ?? [];
  const wall = wallQuery.data?.data ?? null;
  const devices = devicesQuery.data?.data ?? [];
  const cellCount = wall ? wall.canvas.rows * wall.canvas.cols : 0;

  const wallColumns: TableProps<WallSummary>["columns"] = [
    {
      title: "Name",
      dataIndex: "name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: "Layout",
      responsive: ["lg"],
      render: (_, w) =>
        `${w.canvas.cols}×${w.canvas.rows} · ${w.canvas.width}×${w.canvas.height}px · ` +
        `${w.members} member${w.members === 1 ? "" : "s"}`,
    },
    {
      title: "Status",
      dataIndex: "status",
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: "Actions",
      align: "right",
      render: (_, w) => (
        <Space size="small">
          <Button size="small" onClick={() => setSelected(selected === w.id ? null : w.id)}>
            {selected === w.id ? "Close" : "Manage"}
          </Button>
          {canManage && (
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => deleteWall.mutate(w.id)}
            >
              Delete
            </Button>
          )}
        </Space>
      ),
    },
  ];

  const memberColumns: TableProps<WallMemberState>["columns"] = [
    { title: "Device", dataIndex: "device_name" },
    {
      title: "Viewport",
      responsive: ["lg"],
      render: (_, m) => (
        <Typography.Text code className="text-xs">
          {m.viewport.x},{m.viewport.y} {m.viewport.width}×{m.viewport.height}
        </Typography.Text>
      ),
    },
    { title: "Role", dataIndex: "role", responsive: ["lg"] },
    {
      title: "Status",
      render: (_, m) => <StatusBadge status={m.online ? "online" : "offline"} />,
    },
    ...(canManage
      ? [
          {
            title: "Actions",
            align: "right" as const,
            render: (_: unknown, m: WallMemberState) => (
              <Button size="small" danger onClick={() => removeMember.mutate(m.member_id)}>
                Remove
              </Button>
            ),
          },
        ]
      : []),
  ];

  return (
    <Space orientation="vertical" size="middle" className="w-full">
      {canManage && (
        <Card size="small">
          <Form
            form={form}
            layout="inline"
            initialValues={{ cols: 2, rows: 1 }}
            onFinish={(values) => {
              setError(null);
              createWall.mutate(values);
            }}
            className="gap-y-2"
          >
            <Form.Item
              name="name"
              label="Wall name"
              rules={[{ required: true, message: "Wall name is required." }]}
            >
              <Input className="w-52" />
            </Form.Item>
            <Form.Item name="cols" label="Columns">
              <InputNumber min={1} max={8} className="w-20" />
            </Form.Item>
            <Form.Item name="rows" label="Rows">
              <InputNumber min={1} max={8} className="w-20" />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                icon={<PlusOutlined />}
                loading={createWall.isPending}
              >
                Create wall (1080p per cell)
              </Button>
            </Form.Item>
          </Form>
        </Card>
      )}

      <Card size="small" title="Video walls">
        <Table<WallSummary>
          size="middle"
          rowKey="id"
          columns={wallColumns}
          dataSource={walls}
          loading={wallsQuery.isLoading}
          scroll={{ x: "max-content" }}
          pagination={false}
          locale={{
            emptyText: (
              <EmptyState
                title="No walls yet"
                description="Create a wall to synchronize playback across a grid of displays."
              />
            ),
          }}
        />

        {wall && selected && (
          <Card size="small" className="mt-3" type="inner">
            <Space orientation="vertical" size="small" className="w-full">
              {wall.status === "degraded" && (
                <Alert
                  type="warning"
                  showIcon
                  message="Wall degraded — one or more members are offline. Healthy members keep playing standalone; sync resumes when they return."
                />
              )}
              <Flex justify="space-between" align="center" wrap gap="small">
                <Space size="small" wrap>
                  <Typography.Text strong>Members — {wall.name}</Typography.Text>
                  {wall.session && (
                    <Typography.Text type="secondary" className="font-mono text-xs">
                      session {wall.session.id.slice(0, 8)} · tolerance{" "}
                      {wall.sync_policy.tolerance_ms}ms
                    </Typography.Text>
                  )}
                </Space>
                {canControl && (
                  <Button
                    type="primary"
                    danger={Boolean(wall.session)}
                    icon={wall.session ? <StopOutlined /> : <CaretRightOutlined />}
                    loading={syncAction.isPending}
                    onClick={() => syncAction.mutate(wall.session ? "stop" : "start")}
                  >
                    {wall.session ? "Stop sync" : "Start sync"}
                  </Button>
                )}
              </Flex>
              <Table<WallMemberState>
                size="small"
                rowKey="member_id"
                columns={memberColumns}
                dataSource={wall.members}
                scroll={{ x: "max-content" }}
                pagination={false}
                locale={{ emptyText: <EmptyState title="No members yet" /> }}
              />
              {canManage && (
                <Space size="small" wrap align="end">
                  <div>
                    <Typography.Text type="secondary" className="block text-xs">
                      Device
                    </Typography.Text>
                    <Select
                      className="mt-0.5 w-44"
                      value={memberForm.device_id || undefined}
                      placeholder="Select…"
                      aria-label="Device"
                      onChange={(value) =>
                        setMemberForm((p) => ({ ...p, device_id: value ?? "" }))
                      }
                      options={devices.map((d) => ({ value: d.id, label: d.name }))}
                    />
                  </div>
                  <div>
                    <Typography.Text type="secondary" className="block text-xs">
                      Cell (0-based)
                    </Typography.Text>
                    <Select
                      className="mt-0.5 w-24"
                      value={memberForm.cell}
                      aria-label="Cell (0-based)"
                      onChange={(value) => setMemberForm((p) => ({ ...p, cell: value }))}
                      options={Array.from({ length: cellCount }, (_, i) => ({
                        value: String(i),
                        label: String(i),
                      }))}
                    />
                  </div>
                  <Button
                    type="primary"
                    disabled={!memberForm.device_id}
                    loading={addMember.isPending}
                    onClick={() => addMember.mutate()}
                  >
                    Add member
                  </Button>
                </Space>
              )}
            </Space>
          </Card>
        )}
      </Card>

      {error && <Alert type="error" message={error} showIcon role="alert" />}
    </Space>
  );
}
