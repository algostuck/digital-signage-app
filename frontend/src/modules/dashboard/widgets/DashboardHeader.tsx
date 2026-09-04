import { ReloadOutlined, SettingOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  DatePicker,
  Drawer,
  Flex,
  Segmented,
  Space,
  Switch,
  Tooltip,
  Typography,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useState } from "react";
import { api } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { PRESET_LABELS, useRelativeAge } from "../api";
import { WIDGETS, type useDashboardLayout } from "../customise";
import type { DashboardRange, RangePreset } from "../types";

interface Membership {
  organization_id: string;
  organization_name: string;
  is_home: boolean;
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export function DashboardHeader({
  range,
  setPreset,
  setCustom,
  generatedAt,
  onRefresh,
  refreshing,
  layout,
}: {
  range: DashboardRange;
  setPreset: (p: RangePreset) => void;
  setCustom: (from: string, to: string) => void;
  generatedAt: string | null;
  onRefresh: () => void;
  refreshing: boolean;
  layout: ReturnType<typeof useDashboardLayout>;
}) {
  const { user } = useAuth();
  const [customiseOpen, setCustomiseOpen] = useState(false);
  const age = useRelativeAge(generatedAt);
  const memberships = useQuery({
    queryKey: ["memberships", user?.id],
    queryFn: () => api.get<Membership[]>("/auth/memberships"),
    enabled: user != null,
    staleTime: 5 * 60 * 1000,
  });
  const activeId = user?.active_organization_id ?? user?.organization_id;
  const orgName = memberships.data?.data?.find((m) => m.organization_id === activeId)?.organization_name;
  const firstName = user?.full_name?.split(" ")[0];

  return (
    <div className="mb-5">
      <Flex wrap justify="space-between" align="flex-start" gap="middle">
        <div className="min-w-0">
          <Typography.Title level={3} className="!mb-0">
            Dashboard
          </Typography.Title>
          <Typography.Text className="block text-[15px]">
            {greeting()}
            {firstName ? `, ${firstName}` : ""}.
          </Typography.Text>
          <Typography.Text type="secondary">
            {orgName ? `${orgName} — ` : ""}the operational overview of your signage network.
          </Typography.Text>
        </div>

        <Space wrap align="center" size="small">
          <Segmented<RangePreset>
            value={range.preset}
            onChange={(value) => (value === "custom" ? setCustom(range.from, range.to) : setPreset(value))}
            options={(Object.keys(PRESET_LABELS) as RangePreset[]).map((key) => ({
              value: key,
              label: PRESET_LABELS[key],
            }))}
            aria-label="Time range"
          />
          {range.preset === "custom" && (
            <DatePicker.RangePicker
              value={[dayjs(range.from), dayjs(range.to)]}
              allowClear={false}
              maxDate={dayjs()}
              onChange={(values: [Dayjs | null, Dayjs | null] | null) => {
                if (values?.[0] && values[1]) {
                  setCustom(values[0].format("YYYY-MM-DD"), values[1].format("YYYY-MM-DD"));
                }
              }}
              aria-label="Custom date range"
            />
          )}
          <Tooltip title={age ? `Updated ${age}` : "Refresh"}>
            <Button icon={<ReloadOutlined />} loading={refreshing} onClick={onRefresh} aria-label="Refresh dashboard">
              {age ? `Updated ${age}` : "Refresh"}
            </Button>
          </Tooltip>
          <Button icon={<SettingOutlined />} onClick={() => setCustomiseOpen(true)}>
            Customise
          </Button>
        </Space>
      </Flex>

      <Drawer
        title="Customise dashboard"
        open={customiseOpen}
        onClose={() => setCustomiseOpen(false)}
        size={380}
        extra={
          <Button onClick={layout.reset} disabled={layout.isDefault}>
            Reset to default
          </Button>
        }
      >
        <Typography.Paragraph type="secondary" className="text-xs">
          Saved on this browser for your account. Hidden sections keep loading in the background;
          they are simply not shown.
        </Typography.Paragraph>
        <ul className="m-0 list-none p-0 divide-y divide-slate-200 dark:divide-slate-700">
          {layout.order.map((key, index) => {
            const widget = WIDGETS.find((w) => w.key === key)!;
            return (
              <li key={key} className="flex items-center gap-2 py-2">
                <Switch
                  size="small"
                  checked={layout.isVisible(key)}
                  onChange={() => layout.toggle(key)}
                  aria-label={`Show ${widget.label}`}
                />
                <span className="flex-1">{widget.label}</span>
                <Button
                  size="small"
                  type="text"
                  disabled={index === 0}
                  onClick={() => layout.move(key, -1)}
                  aria-label={`Move ${widget.label} up`}
                >
                  ↑
                </Button>
                <Button
                  size="small"
                  type="text"
                  disabled={index === layout.order.length - 1}
                  onClick={() => layout.move(key, 1)}
                  aria-label={`Move ${widget.label} down`}
                >
                  ↓
                </Button>
              </li>
            );
          })}
        </ul>
      </Drawer>
    </div>
  );
}
