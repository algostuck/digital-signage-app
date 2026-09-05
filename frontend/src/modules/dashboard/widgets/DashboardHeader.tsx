import { ArrowDownOutlined, ArrowUpOutlined, ReloadOutlined, SettingOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Button, DatePicker, Drawer, Flex, Segmented, Space, Switch, Tooltip, Typography } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useState } from "react";
import { DRAWER, EntityList, PageHeader } from "@/design-system";
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

/** The dashboard's page header on the shared PageHeader: greeting as the
 * description, range / refresh / customise as the (secondary) actions —
 * the dashboard has no create action, so no primary button. */
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
    <>
      <PageHeader
        title="Dashboard"
        description={`${greeting()}${firstName ? `, ${firstName}` : ""}. ${
          orgName ? `${orgName} — ` : ""
        }the operational overview of your signage network.`}
        actions={
          <Space wrap align="center" size="small" style={{ maxWidth: "100%" }} styles={{ item: { minWidth: 0, maxWidth: "100%" } }}>
            {/* Six presets are wider than a phone; scroll the control rather
                than let it push the page sideways. */}
            <div style={{ maxWidth: "100%", minWidth: 0, overflowX: "auto" }}>
              <Segmented<RangePreset>
                value={range.preset}
                onChange={(value) => (value === "custom" ? setCustom(range.from, range.to) : setPreset(value))}
                options={(Object.keys(PRESET_LABELS) as RangePreset[]).map((key) => ({
                  value: key,
                  label: PRESET_LABELS[key],
                }))}
                aria-label="Time range"
              />
            </div>
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
        }
      />

      <Drawer
        title="Customise dashboard"
        open={customiseOpen}
        onClose={() => setCustomiseOpen(false)}
        size={DRAWER.filters}
        extra={
          <Button onClick={layout.reset} disabled={layout.isDefault}>
            Reset to default
          </Button>
        }
      >
        <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
          Saved on this browser for your account. Hidden sections keep loading in the background;
          they are simply not shown.
        </Typography.Paragraph>
        <EntityList
          items={layout.order.map((key, index) => ({ key, index }))}
          rowKey="key"
          dense
          aria-label="Dashboard sections"
          renderItem={({ key, index }) => {
            const widget = WIDGETS.find((w) => w.key === key)!;
            return (
              <Flex align="center" gap={8}>
                <Switch
                  size="small"
                  checked={layout.isVisible(key)}
                  onChange={() => layout.toggle(key)}
                  aria-label={`Show ${widget.label}`}
                />
                <span style={{ flex: 1 }}>{widget.label}</span>
                <Button
                  size="small"
                  type="text"
                  icon={<ArrowUpOutlined />}
                  disabled={index === 0}
                  onClick={() => layout.move(key, -1)}
                  aria-label={`Move ${widget.label} up`}
                />
                <Button
                  size="small"
                  type="text"
                  icon={<ArrowDownOutlined />}
                  disabled={index === layout.order.length - 1}
                  onClick={() => layout.move(key, 1)}
                  aria-label={`Move ${widget.label} down`}
                />
              </Flex>
            );
          }}
        />
      </Drawer>
    </>
  );
}
