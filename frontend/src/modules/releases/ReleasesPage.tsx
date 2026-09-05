import { PlusOutlined, RollbackOutlined, UploadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Flex,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Progress,
  Result,
  Select,
  Space,
  Typography,
  Upload,
} from "antd";
import { useState } from "react";
import { PageHeader } from "@/design-system";
import { EmptyState, LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { timeAgo, type DeviceGroup } from "../devices/types";

interface RingDevices {
  total: number;
  pending: number;
  updating: number;
  succeeded: number;
  failed: number;
}

interface Ring {
  id: string;
  ring_no: number;
  percentage: number;
  failure_threshold_pct: number;
  state: string;
  started_at: string | null;
  completed_at: string | null;
  devices: RingDevices;
}

interface Release {
  id: string;
  version: string;
  state: string;
  notes: string | null;
  checksum: string;
  size_bytes: number;
  created_at: string;
  rollout: Ring[];
}

interface RingDeviceRow {
  device_id: string;
  device_name: string;
  state: string;
  failure_reason: string | null;
}

interface UploadSession {
  upload_session_id: string;
  upload_url: string;
  headers: Record<string, string>;
  asset_id: string;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${bytes} B`;
}

/** P2-05 Player Update Center: packages, rollout rings, progress, rollback. */
export function ReleasesPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("releases.manage");
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [rolloutFor, setRolloutFor] = useState<Release | null>(null);

  const releasesQuery = useQuery({
    queryKey: ["player-releases"],
    queryFn: () => api.get<Release[]>("/player-releases"),
    enabled: canManage,
    refetchInterval: 15_000,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["player-releases"] });
  const releases = releasesQuery.data?.data ?? [];

  if (!canManage) {
    return (
      <Result
        status="403"
        title="Update Center unavailable"
        subTitle="You need the releases.manage permission to use the Update Center."
      />
    );
  }

  return (
    <div>
      <PageHeader
        title="Player Update Center"
        description="Upload player packages and roll them out in staged rings with stop-on-failure protection."
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowCreate(true)}>
            New release
          </Button>
        }
      />

      {releasesQuery.isLoading ? (
        <LoadingState rows={5} />
      ) : releases.length === 0 ? (
        <Card>
          <EmptyState
            title="No player releases yet"
            description="Upload a package to get started."
            action={
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowCreate(true)}>
                New release
              </Button>
            }
          />
        </Card>
      ) : (
        <Space orientation="vertical" size="middle" className="w-full">
          {releases.map((release) => (
            <ReleaseCard
              key={release.id}
              release={release}
              onStartRollout={() => setRolloutFor(release)}
              onChanged={refresh}
            />
          ))}
        </Space>
      )}

      {showCreate && (
        <CreateReleaseModal onClose={() => setShowCreate(false)} onCreated={refresh} />
      )}
      {rolloutFor && (
        <StartRolloutModal
          release={rolloutFor}
          onClose={() => setRolloutFor(null)}
          onStarted={refresh}
        />
      )}
    </div>
  );
}

function ReleaseCard({
  release,
  onStartRollout,
  onChanged,
}: {
  release: Release;
  onStartRollout: () => void;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const rollback = useMutation({
    mutationFn: () => api.post(`/player-releases/${release.id}/rollback`),
    onSuccess: onChanged,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Rollback failed"),
  });
  const hasRollout = release.rollout.length > 0;

  return (
    <Card size="small">
      <Flex wrap align="center" gap="small">
        <Typography.Text strong code>
          {release.version}
        </Typography.Text>
        <StatusBadge status={release.state} />
        <Typography.Text type="secondary" className="text-xs">
          {formatBytes(release.size_bytes)} · created {timeAgo(release.created_at)}
        </Typography.Text>
        <Space className="ms-auto">
          {!hasRollout && release.state !== "rolled_back" && (
            <Button type="primary" size="small" onClick={onStartRollout}>
              Start rollout
            </Button>
          )}
          {release.state === "active" && (
            <Popconfirm
              title={`Roll back ${release.version}?`}
              description="The rollout halts and the update is withdrawn."
              onConfirm={() => rollback.mutate()}
              okButtonProps={{ danger: true }}
            >
              <Button size="small" danger icon={<RollbackOutlined />}>
                Roll back
              </Button>
            </Popconfirm>
          )}
        </Space>
      </Flex>
      {release.notes && (
        <Typography.Paragraph type="secondary" className="!mb-0 !mt-1">
          {release.notes}
        </Typography.Paragraph>
      )}
      {error && <Alert type="error" message={error} showIcon className="mt-2" role="alert" />}
      {hasRollout && (
        <Space orientation="vertical" size="small" className="mt-3 w-full">
          {release.rollout.map((ring) => (
            <RingRow key={ring.id} ring={ring} />
          ))}
        </Space>
      )}
    </Card>
  );
}

function RingRow({ ring }: { ring: Ring }) {
  const [expanded, setExpanded] = useState(false);
  const devicesQuery = useQuery({
    queryKey: ["rollout-ring", ring.id],
    queryFn: () => api.get<RingDeviceRow[]>(`/rollouts/${ring.id}`),
    enabled: expanded,
  });
  const done = ring.devices.succeeded + ring.devices.failed;
  const progressPct = ring.devices.total ? Math.round((done / ring.devices.total) * 100) : 0;

  return (
    <div>
      <Flex
        wrap
        align="center"
        gap="small"
        component="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full cursor-pointer border-0 bg-transparent p-0 text-left"
        aria-expanded={expanded}
      >
        <Typography.Text strong>
          Ring {ring.ring_no} · {ring.percentage}%
        </Typography.Text>
        <StatusBadge status={ring.state} />
        <Typography.Text type="secondary" className="text-xs">
          {ring.devices.succeeded}/{ring.devices.total} succeeded
          {ring.devices.failed > 0 && ` · ${ring.devices.failed} failed`}
          {" · "}threshold {ring.failure_threshold_pct}%
        </Typography.Text>
        <Progress
          percent={progressPct}
          size="small"
          className="ms-auto max-w-36"
          status={ring.state === "stopped" ? "exception" : undefined}
        />
      </Flex>
      {expanded &&
        (devicesQuery.isLoading ? (
          <LoadingState rows={2} />
        ) : (
          <List
            size="small"
            className="mt-2"
            dataSource={devicesQuery.data?.data ?? []}
            renderItem={(row) => (
              <List.Item className="!px-0 !py-1">
                <Space size="small">
                  <Typography.Text>{row.device_name}</Typography.Text>
                  <StatusBadge status={row.state} />
                  {row.failure_reason && (
                    <Typography.Text type="danger" className="text-xs">
                      {row.failure_reason}
                    </Typography.Text>
                  )}
                </Space>
              </List.Item>
            )}
          />
        ))}
    </div>
  );
}

function CreateReleaseModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form] = Form.useForm<{ version: string; notes?: string }>();
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<"idle" | "uploading" | "creating">("idle");
  const [error, setError] = useState<string | null>(null);

  async function submit(values: { version: string; notes?: string }) {
    if (!file) {
      setError("A package file is required.");
      return;
    }
    setError(null);
    setPhase("uploading");
    try {
      const envelope = await api.post<UploadSession>("/assets/uploads", {
        filename: file.name,
        mime_type: file.type || "application/zip",
        size_bytes: file.size,
        name: `Player package ${values.version.trim()}`,
      });
      const session = envelope.data!;
      const put = await fetch(session.upload_url, {
        method: "PUT",
        headers: session.headers,
        body: file,
      });
      if (!put.ok) throw new Error(`Package upload failed (${put.status})`);
      await api.post(`/assets/uploads/${session.upload_session_id}/complete`);

      setPhase("creating");
      await api.post("/player-releases", {
        version: values.version.trim(),
        package_asset_id: session.asset_id,
        notes: values.notes?.trim() || null,
      });
      onCreated();
      onClose();
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Release creation failed",
      );
      setPhase("idle");
    }
  }

  return (
    <Modal
      title="New player release"
      open
      onCancel={onClose}
      okText={phase === "uploading" ? "Uploading…" : phase === "creating" ? "Creating…" : "Create release"}
      confirmLoading={phase !== "idle"}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
      <Form form={form} layout="vertical" onFinish={submit}>
        <Form.Item
          name="version"
          label="Version"
          rules={[{ required: true, message: "Version is required." }]}
        >
          <Input placeholder="e.g. 2.5.0" autoFocus />
        </Form.Item>
        <Form.Item label="Package (.zip)" required>
          <Upload.Dragger
            accept=".zip,application/zip"
            maxCount={1}
            beforeUpload={(f) => {
              setFile(f);
              return false;
            }}
            onRemove={() => setFile(null)}
          >
            <p className="ant-upload-drag-icon">
              <UploadOutlined />
            </p>
            <p className="ant-upload-text">Click or drag the package file here</p>
          </Upload.Dragger>
        </Form.Item>
        <Form.Item name="notes" label="Notes (optional)">
          <Input.TextArea rows={2} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

function StartRolloutModal({
  release,
  onClose,
  onStarted,
}: {
  release: Release;
  onClose: () => void;
  onStarted: () => void;
}) {
  const [form] = Form.useForm<{ group_id?: string; rings: string; threshold: number }>();
  const [error, setError] = useState<string | null>(null);

  const groupsQuery = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<DeviceGroup[]>("/device-groups"),
  });

  const start = useMutation({
    mutationFn: (values: { group_id?: string; rings: string; threshold: number }) => {
      const parsed = values.rings
        .split(",")
        .map((part) => Number.parseInt(part.trim(), 10))
        .filter((n) => !Number.isNaN(n));
      return api.post(`/player-releases/${release.id}/rollouts`, {
        group_id: values.group_id || null,
        rings: parsed,
        failure_threshold_pct: values.threshold || 0,
      });
    },
    onSuccess: () => {
      onStarted();
      onClose();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Rollout failed to start"),
  });

  return (
    <Modal
      title={`Roll out ${release.version}`}
      open
      onCancel={onClose}
      okText="Start rollout"
      confirmLoading={start.isPending}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
      <Form
        form={form}
        layout="vertical"
        initialValues={{ rings: "10, 50, 100", threshold: 5 }}
        onFinish={(values) => {
          setError(null);
          start.mutate(values);
        }}
      >
        <Form.Item name="group_id" label="Target">
          <Select
            allowClear
            placeholder="All active devices"
            options={(groupsQuery.data?.data ?? []).map((group) => ({
              value: group.id,
              label: group.name,
            }))}
          />
        </Form.Item>
        <Flex gap="middle">
          <Form.Item
            name="rings"
            label="Rings (cumulative %)"
            className="flex-1"
            extra="Comma-separated, increasing, ending at 100."
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="threshold"
            label="Failure threshold %"
            className="flex-1"
            extra="A ring exceeding this failure share stops the rollout."
          >
            <InputNumber min={0} max={100} className="w-full" />
          </Form.Item>
        </Flex>
      </Form>
    </Modal>
  );
}
