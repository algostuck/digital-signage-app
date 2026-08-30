export interface DeviceGroup {
  id: string;
  name: string;
  description: string | null;
}

export interface DeviceCapability {
  capability_code: string;
  supported: boolean;
  value_json: Record<string, unknown> | null;
}

export interface Device {
  id: string;
  location_id: string | null;
  name: string;
  manufacturer: string | null;
  model: string | null;
  platform: string | null;
  os_version: string | null;
  player_version: string | null;
  serial_no: string;
  mac_address: string | null;
  ip_address: string | null;
  orientation: string | null;
  screen_width: number | null;
  screen_height: number | null;
  timezone: string | null;
  status: string;
  approved_at: string | null;
  last_heartbeat_at: string | null;
  created_at: string;
  group: DeviceGroup | null;
  tags: { id: string; key: string; value: string }[];
  connection_status: string;
}

export interface DeviceDetail extends Device {
  capabilities: DeviceCapability[];
  last_heartbeat_json: Record<string, unknown> | null;
  has_credential: boolean;
}

export interface DeviceCommand {
  id: string;
  command_type: string;
  payload_json: Record<string, unknown> | null;
  status: string;
  created_at: string;
  sent_at: string | null;
  acknowledged_at: string | null;
  result_json: Record<string, unknown> | null;
}

export function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  // Timestamps without an offset are UTC by API contract.
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const seconds = Math.max(0, (Date.now() - new Date(normalized).getTime()) / 1000);
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h ago`;
  return `${Math.round(seconds / 86400)}d ago`;
}
