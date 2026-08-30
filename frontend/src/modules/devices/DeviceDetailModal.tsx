import { SendOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Flex,
  Image,
  List,
  Popconfirm,
  Select,
  Space,
  Tag,
  Timeline,
  Typography,
} from "antd";
import { useState } from "react";
import { LoadingState } from "../../components/ui/states";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { LocationNode } from "../locations/types";
import { timeAgo, type DeviceCommand, type DeviceDetail, type DeviceGroup } from "./types";

const COMMAND_TYPES = [
  "RESTART_PLAYER",
  "RESTART_DEVICE",
  "SYNC_NOW",
  "CLEAR_CACHE",
  "SCREENSHOT",
  "VOLUME_SET",
];

interface Props {
  deviceId: string;
  onClose: () => void;
  onChanged: () => void;
}

function SectionLabel({ children }: { children: string }) {
  return (
    <Typography.Text type="secondary" className="text-xs font-medium uppercase tracking-wide">
      {children}
    </Typography.Text>
  );
}

/** SCR-09 Device Details: health, capabilities, assignment, commands. */
export function DeviceDetailModal({ deviceId, onClose, onChanged }: Props) {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("devices.manage");
  const canControl = hasPermission("devices.control");
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [commandType, setCommandType] = useState(COMMAND_TYPES[0]);

  const deviceQuery = useQuery({
    queryKey: ["device", deviceId],
    queryFn: () => api.get<DeviceDetail>(`/devices/${deviceId}`),
  });
  const commandsQuery = useQuery({
    queryKey: ["device-commands", deviceId],
    queryFn: () => api.get<DeviceCommand[]>(`/devices/${deviceId}/commands`),
  });
  const screenshotsQuery = useQuery({
    queryKey: ["device-screenshots", deviceId],
    queryFn: () =>
      api.get<{ id: string; url: string; captured_at: string }[]>(
        `/devices/${deviceId}/screenshots`,
      ),
  });
  const eventsQuery = useQuery({
    queryKey: ["device-events", deviceId],
    queryFn: () =>
      api.get<
        { at: string; kind: string; type: string; title: string; state?: string }[]
      >(`/devices/${deviceId}/events?limit=20`),
  });
  const locationsQuery = useQuery({
    queryKey: ["locations-flat"],
    queryFn: () => api.get<LocationNode[]>("/locations?page_size=200"),
    enabled: canManage,
  });
  const groupsQuery = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<DeviceGroup[]>("/device-groups"),
    enabled: canManage,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["device", deviceId] });
    queryClient.invalidateQueries({ queryKey: ["device-commands", deviceId] });
    onChanged();
  };

  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");

  const assignLocation = useMutation({
    mutationFn: (locationId: string | null) =>
      api.post(`/devices/${deviceId}/assign-location`, { location_id: locationId }),
    onSuccess: refresh,
    onError,
  });
  const assignGroup = useMutation({
    mutationFn: (groupId: string | null) =>
      api.patch(`/devices/${deviceId}`, groupId ? { group_id: groupId } : { clear_group: true }),
    onSuccess: refresh,
    onError,
  });
  const lifecycle = useMutation({
    mutationFn: (verb: string) => api.post(`/devices/${deviceId}/${verb}`),
    onSuccess: refresh,
    onError,
  });
  const sendCommand = useMutation({
    mutationFn: () => api.post(`/devices/${deviceId}/commands`, { command_type: commandType }),
    onSuccess: refresh,
    onError,
  });

  const device = deviceQuery.data?.data ?? null;
  if (!device) {
    return (
      <Drawer title="Device details" open onClose={onClose} size={640} placement="right">
        <LoadingState rows={8} />
      </Drawer>
    );
  }

  const screenshots = screenshotsQuery.data?.data ?? [];
  const events = eventsQuery.data?.data ?? [];
  const commands = commandsQuery.data?.data ?? [];

  return (
    <Drawer
      title={device.name}
      open
      onClose={onClose}
      width={640}
      placement="right"
      footer={
        canManage ? (
          <Flex wrap justify="flex-end" gap="small">
            {device.status === "active" && (
              <Popconfirm
                title="Reset this device's credential?"
                description="It will re-enroll on next poll."
                onConfirm={() => lifecycle.mutate("reset-token")}
              >
                <Button loading={lifecycle.isPending}>Reset credential</Button>
              </Popconfirm>
            )}
            {device.status !== "decommissioned" && (
              <Popconfirm
                title={`Decommission "${device.name}"?`}
                description="This revokes its credential."
                onConfirm={() => lifecycle.mutate("decommission")}
                okButtonProps={{ danger: true }}
              >
                <Button danger>Decommission</Button>
              </Popconfirm>
            )}
          </Flex>
        ) : undefined
      }
    >
      <Space orientation="vertical" size="middle" className="w-full">
        <Space size="small" wrap align="center">
          <StatusBadge status={device.status} />
          <StatusBadge status={device.connection_status} />
          <Typography.Text type="secondary" className="text-xs">
            Heartbeat {timeAgo(device.last_heartbeat_at)}
          </Typography.Text>
          {device.has_credential && <Tag variant="filled">credential issued</Tag>}
        </Space>

        <Descriptions
          size="small"
          column={{ xs: 1, sm: 2 }}
          items={[
            {
              label: "Serial",
              children: (
                <Typography.Text code className="text-xs">
                  {device.serial_no}
                </Typography.Text>
              ),
            },
            { label: "Platform", children: device.platform ?? "—" },
            {
              label: "Hardware",
              children: [device.manufacturer, device.model].filter(Boolean).join(" ") || "—",
            },
            { label: "Player", children: device.player_version ?? "—" },
            { label: "OS", children: device.os_version ?? "—" },
            {
              label: "IP",
              children: device.ip_address ? (
                <Typography.Text code className="text-xs">
                  {device.ip_address}
                </Typography.Text>
              ) : (
                "—"
              ),
            },
            {
              label: "Resolution",
              children:
                device.screen_width && device.screen_height
                  ? `${device.screen_width}×${device.screen_height}`
                  : "—",
            },
            { label: "Timezone", children: device.timezone ?? "inherited" },
          ]}
        />

        {canManage && device.status === "active" && (
          <Flex gap="middle" wrap>
            <div className="min-w-0 flex-1">
              <SectionLabel>Location</SectionLabel>
              <Select
                className="mt-1 w-full"
                aria-label="Location"
                value={device.location_id ?? ""}
                onChange={(value) => assignLocation.mutate(value || null)}
                options={[
                  { value: "", label: "— unassigned —" },
                  ...(locationsQuery.data?.data ?? []).map((loc) => ({
                    value: loc.id,
                    label: loc.name,
                  })),
                ]}
              />
            </div>
            <div className="min-w-0 flex-1">
              <SectionLabel>Group</SectionLabel>
              <Select
                className="mt-1 w-full"
                aria-label="Group"
                value={device.group?.id ?? ""}
                onChange={(value) => assignGroup.mutate(value || null)}
                options={[
                  { value: "", label: "— no group —" },
                  ...(groupsQuery.data?.data ?? []).map((g) => ({
                    value: g.id,
                    label: g.name,
                  })),
                ]}
              />
            </div>
          </Flex>
        )}

        {screenshots.length > 0 && (
          <div>
            <SectionLabel>Latest screenshot evidence</SectionLabel>
            <div className="mt-1">
              <Image
                src={screenshots[0].url}
                alt={`Screen of ${device.name}`}
                height={160}
                className="rounded-md border border-slate-200 object-contain"
              />
            </div>
            <Typography.Paragraph type="secondary" className="!mb-0 mt-1 text-xs">
              captured {timeAgo(screenshots[0].captured_at)} · {screenshots.length} on record
            </Typography.Paragraph>
          </div>
        )}

        {device.capabilities.length > 0 && (
          <div>
            <SectionLabel>Capabilities</SectionLabel>
            <div className="mt-1">
              <Space size={[4, 8]} wrap>
                {device.capabilities.map((c) => (
                  <Tag
                    key={c.capability_code}
                    variant="filled"
                    color={c.supported ? "success" : "default"}
                    className={c.supported ? undefined : "line-through"}
                  >
                    {c.capability_code}
                  </Tag>
                ))}
              </Space>
            </div>
          </div>
        )}

        {canControl && device.status === "active" && (
          <div>
            <SectionLabel>Remote command</SectionLabel>
            <Space.Compact className="mt-1 w-full">
              <Select
                className="flex-1"
                aria-label="Remote command"
                value={commandType}
                onChange={setCommandType}
                options={COMMAND_TYPES.map((c) => ({ value: c, label: c }))}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={() => sendCommand.mutate()}
                loading={sendCommand.isPending}
              >
                Queue
              </Button>
            </Space.Compact>
          </div>
        )}

        {events.length > 0 && (
          <div>
            <SectionLabel>Event timeline</SectionLabel>
            <div className="mt-2 max-h-48 overflow-y-auto">
              <Timeline
                items={events.map((row) => ({
                  color:
                    row.kind === "incident" ? "red" : row.kind === "recovery" ? "green" : "gray",
                  children: (
                    <Space size="small" wrap>
                      <Typography.Text code className="text-xs">
                        {row.type}
                      </Typography.Text>
                      <Typography.Text>{row.title}</Typography.Text>
                      <Typography.Text type="secondary" className="text-xs">
                        {timeAgo(row.at)}
                      </Typography.Text>
                    </Space>
                  ),
                }))}
              />
            </div>
          </div>
        )}

        {commands.length > 0 && (
          <div>
            <SectionLabel>Recent commands</SectionLabel>
            <List
              size="small"
              dataSource={commands.slice(0, 5)}
              renderItem={(c) => (
                <List.Item className="!px-0 !py-1">
                  <Space size="small">
                    <Typography.Text code className="text-xs">
                      {c.command_type}
                    </Typography.Text>
                    <StatusBadge status={c.status} />
                    <Typography.Text type="secondary" className="text-xs">
                      {timeAgo(c.created_at)}
                    </Typography.Text>
                  </Space>
                </List.Item>
              )}
            />
          </div>
        )}

        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Space>
    </Drawer>
  );
}
