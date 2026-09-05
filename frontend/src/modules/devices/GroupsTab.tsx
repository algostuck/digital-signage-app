import { PlusOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Flex,
  Input,
  Modal,
  Popconfirm,
  Radio,
  Row,
  Select,
  Space,
  Typography,
} from "antd";
import { ToneTag } from "@/design-system";
import { toneOf } from "@/design-system";
import { useState } from "react";
import { EmptyState, LoadingState } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { LocationNode } from "../locations/types";
import type { DeviceGroup } from "./types";

const RULE_FIELDS = ["manufacturer", "platform", "model", "status", "tag", "location"] as const;
const BULK_COMMANDS = ["SYNC_NOW", "RESTART_PLAYER", "RESTART_DEVICE", "CLEAR_CACHE", "SCREENSHOT"];

interface RuleCondition {
  field: (typeof RULE_FIELDS)[number];
  operator: string;
  value: string;
  tagKey?: string;
  tagValue?: string;
}

interface GroupRow extends DeviceGroup {
  group_type: string;
  rule_json: Record<string, unknown> | null;
  member_count: number;
}

/** P2-04 Device Group Builder: static + dynamic rules with preview. */
export function GroupsTab() {
  const { hasPermission } = useAuth();
  const { message } = App.useApp();
  const canManage = hasPermission("devices.manage");
  const canControl = hasPermission("devices.control");
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [actionGroup, setActionGroup] = useState<GroupRow | null>(null);
  const [command, setCommand] = useState(BULK_COMMANDS[0]);

  const groupsQuery = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<GroupRow[]>("/device-groups"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["device-groups"] });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/device-groups/${id}`),
    onSuccess: invalidate,
    onError: (err) =>
      message.error(err instanceof ApiError ? err.message : "Failed to delete group"),
  });
  const runAction = useMutation({
    mutationFn: ({ id, command_type }: { id: string; command_type: string }) =>
      api.post<{ queued: number; skipped: number }>(`/device-groups/${id}/actions`, {
        command_type,
      }),
    onSuccess: (envelope) => {
      message.success(
        `Queued for ${envelope.data!.queued} device(s)` +
          (envelope.data!.skipped ? ` (${envelope.data!.skipped} inactive skipped)` : ""),
      );
      setActionGroup(null);
    },
    onError: (err) =>
      message.error(err instanceof ApiError ? err.message : "Bulk action failed"),
  });

  if (groupsQuery.isLoading) return <LoadingState rows={4} />;
  const groups = groupsQuery.data?.data ?? [];

  return (
    <div>
      {canManage && (
        <Flex justify="flex-end" className="mb-3">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            Add group
          </Button>
        </Flex>
      )}
      {groups.length === 0 ? (
        <Card>
          <EmptyState
            title="No device groups yet"
            description="Static groups hold assigned devices; dynamic groups match rules like manufacturer or location subtree."
          />
        </Card>
      ) : (
        <Row gutter={[12, 12]}>
          {groups.map((group) => (
            <Col key={group.id} xs={24} sm={12} lg={8}>
              <Card size="small">
                <Flex justify="space-between" align="flex-start" gap="small">
                  <div className="min-w-0">
                    <Typography.Text strong ellipsis className="block">
                      {group.name}
                    </Typography.Text>
                    <Space size="small" className="mt-1">
                      <ToneTag tone={toneOf(group.group_type === "dynamic" ? "blue" : "default")}
                      >
                        {group.group_type}
                      </ToneTag>
                      <Typography.Text type="secondary" className="text-sm">
                        {group.member_count} device{group.member_count === 1 ? "" : "s"}
                      </Typography.Text>
                    </Space>
                  </div>
                  {canManage && (
                    <Popconfirm
                      title={`Delete group "${group.name}"?`}
                      onConfirm={() => remove.mutate(group.id)}
                      okButtonProps={{ danger: true }}
                    >
                      <Button type="link" danger size="small">
                        Delete
                      </Button>
                    </Popconfirm>
                  )}
                </Flex>
                {canControl && group.member_count > 0 && (
                  <Button
                    className="mt-3"
                    size="small"
                    icon={<ThunderboltOutlined />}
                    onClick={() => setActionGroup(group)}
                  >
                    Bulk action…
                  </Button>
                )}
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {createOpen && (
        <GroupBuilderModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            invalidate();
            setCreateOpen(false);
          }}
        />
      )}
      {actionGroup && (
        <Modal
          title={`Bulk action: ${actionGroup.name}`}
          open
          onCancel={() => setActionGroup(null)}
          okText="Queue command"
          confirmLoading={runAction.isPending}
          onOk={() => runAction.mutate({ id: actionGroup.id, command_type: command })}
          destroyOnHidden
        >
          <Space orientation="vertical" size="middle" className="w-full">
            <Typography.Text type="secondary">
              Queue a remote command for all {actionGroup.member_count} active member device(s).
            </Typography.Text>
            <Select
              className="w-full"
              value={command}
              onChange={setCommand}
              aria-label="Command"
              options={BULK_COMMANDS.map((c) => ({ value: c, label: c }))}
            />
          </Space>
        </Modal>
      )}
    </div>
  );
}

function GroupBuilderModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [groupType, setGroupType] = useState<"static" | "dynamic">("static");
  const [match, setMatch] = useState<"all" | "any">("all");
  const [conditions, setConditions] = useState<RuleCondition[]>([
    { field: "manufacturer", operator: "eq", value: "" },
  ]);
  const [preview, setPreview] = useState<{ count: number; sample: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const locationsQuery = useQuery({
    queryKey: ["locations-flat"],
    queryFn: () => api.get<LocationNode[]>("/locations?page_size=200"),
    enabled: groupType === "dynamic",
  });

  function buildRule() {
    return {
      match,
      conditions: conditions.map((condition) => ({
        field: condition.field,
        operator: condition.operator,
        value:
          condition.field === "tag"
            ? { key: condition.tagKey ?? "", value: condition.tagValue ?? "" }
            : condition.value,
      })),
    };
  }

  const previewMutation = useMutation({
    mutationFn: () =>
      api.post<{ count: number; sample: string[] }>("/device-groups/preview", {
        rule_json: buildRule(),
      }),
    onSuccess: (envelope) => {
      setPreview(envelope.data!);
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Preview failed"),
  });

  const create = useMutation({
    mutationFn: () =>
      api.post("/device-groups", {
        name,
        group_type: groupType,
        rule_json: groupType === "dynamic" ? buildRule() : null,
      }),
    onSuccess: onCreated,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to create group"),
  });

  function updateCondition(index: number, patch: Partial<RuleCondition>) {
    setConditions((prev) =>
      prev.map((condition, i) => (i === index ? { ...condition, ...patch } : condition)),
    );
    setPreview(null);
  }

  return (
    <Modal
      title="New device group"
      open
      onCancel={onClose}
      okText="Create group"
      okButtonProps={{ disabled: !name.trim() }}
      confirmLoading={create.isPending}
      onOk={() => {
        setError(null);
        create.mutate();
      }}
      destroyOnHidden
    >
      <Space orientation="vertical" size="middle" className="w-full">
        <div>
          <Typography.Text type="secondary" className="text-xs font-medium uppercase tracking-wide">
            Name
          </Typography.Text>
          <Input
            className="mt-1"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-label="Name"
            autoFocus
          />
        </div>
        <div role="radiogroup" aria-label="Group type">
          <Radio.Group
            value={groupType}
            onChange={(e) => setGroupType(e.target.value as "static" | "dynamic")}
            optionType="button"
            buttonStyle="solid"
            options={[
              { value: "static", label: "Static" },
              { value: "dynamic", label: "Dynamic" },
            ]}
          />
        </div>

        {groupType === "dynamic" && (
          <Card size="small">
            <Space orientation="vertical" size="small" className="w-full">
              <Space size="small" align="center">
                <Typography.Text type="secondary">Match</Typography.Text>
                <Select
                  size="small"
                  value={match}
                  onChange={(value) => setMatch(value)}
                  aria-label="Match mode"
                  options={[
                    { value: "all", label: "all" },
                    { value: "any", label: "any" },
                  ]}
                />
                <Typography.Text type="secondary">of the conditions:</Typography.Text>
              </Space>
              {conditions.map((condition, index) => (
                <Space key={index} size="small" wrap>
                  <Select
                    size="small"
                    className="w-32"
                    value={condition.field}
                    aria-label="Condition field"
                    onChange={(value) =>
                      updateCondition(index, {
                        field: value as RuleCondition["field"],
                        operator: value === "location" ? "in_subtree" : "eq",
                        value: "",
                      })
                    }
                    options={RULE_FIELDS.map((f) => ({ value: f, label: f }))}
                  />
                  <Select
                    size="small"
                    className="w-28"
                    value={condition.operator}
                    aria-label="Condition operator"
                    onChange={(value) => updateCondition(index, { operator: value })}
                    options={(condition.field === "location"
                      ? ["in_subtree", "eq"]
                      : condition.field === "tag"
                        ? ["eq", "ne"]
                        : ["eq", "ne", "contains"]
                    ).map((op) => ({ value: op, label: op }))}
                  />
                  {condition.field === "location" ? (
                    <Select
                      size="small"
                      className="min-w-36"
                      value={condition.value || undefined}
                      placeholder="— location —"
                      aria-label="Location"
                      onChange={(value) => updateCondition(index, { value: value ?? "" })}
                      options={(locationsQuery.data?.data ?? []).map((loc) => ({
                        value: loc.id,
                        label: loc.name,
                      }))}
                    />
                  ) : condition.field === "tag" ? (
                    <>
                      <Input
                        size="small"
                        className="w-24"
                        placeholder="key"
                        value={condition.tagKey ?? ""}
                        onChange={(e) => updateCondition(index, { tagKey: e.target.value })}
                      />
                      <Input
                        size="small"
                        className="w-24"
                        placeholder="value"
                        value={condition.tagValue ?? ""}
                        onChange={(e) => updateCondition(index, { tagValue: e.target.value })}
                      />
                    </>
                  ) : (
                    <Input
                      size="small"
                      className="w-32"
                      placeholder="value"
                      value={condition.value}
                      onChange={(e) => updateCondition(index, { value: e.target.value })}
                    />
                  )}
                  {conditions.length > 1 && (
                    <Button
                      type="link"
                      danger
                      size="small"
                      onClick={() => {
                        setConditions((prev) => prev.filter((_, i) => i !== index));
                        setPreview(null);
                      }}
                    >
                      remove
                    </Button>
                  )}
                </Space>
              ))}
              <Space size="small" wrap align="center">
                <Button
                  type="link"
                  size="small"
                  icon={<PlusOutlined />}
                  onClick={() =>
                    setConditions((prev) => [
                      ...prev,
                      { field: "platform", operator: "eq", value: "" },
                    ])
                  }
                >
                  condition
                </Button>
                <Button
                  size="small"
                  loading={previewMutation.isPending}
                  onClick={() => previewMutation.mutate()}
                >
                  Preview matches
                </Button>
                {preview && (
                  <Typography.Text type="secondary">
                    {preview.count} device{preview.count === 1 ? "" : "s"}
                    {preview.sample.length > 0 && ` — ${preview.sample.join(", ")}`}
                  </Typography.Text>
                )}
              </Space>
            </Space>
          </Card>
        )}

        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Space>
    </Modal>
  );
}
