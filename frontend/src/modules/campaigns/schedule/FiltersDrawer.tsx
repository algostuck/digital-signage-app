import { useQuery } from "@tanstack/react-query";
import { Button, Drawer, Form, Segmented, Select, Space, Switch, TreeSelect, Typography } from "antd";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import type { DeviceGroup } from "../../devices/types";
import type { TreeEntry } from "../../locations/types";
import type { CampaignSummary } from "../types";
import { PRIORITY_BANDS, STATUS_LABEL } from "./palette";
import { EMPTY_FILTERS, type ScheduleFilters } from "./useScheduleWorkspace";

interface TreeOption {
  value: string;
  title: string;
  children?: TreeOption[];
}

function toTree(entries: TreeEntry[]): TreeOption[] {
  return entries.map((entry) => ({
    value: entry.node.id,
    title: entry.node.name,
    children: entry.children.length ? toTree(entry.children) : undefined,
  }));
}

function bandOf(filters: ScheduleFilters): string {
  if (filters.priority_min === undefined && filters.priority_max === undefined) return "";
  return `${filters.priority_min ?? 1}-${filters.priority_max ?? 100}`;
}

/**
 * Every filter is a real query parameter of the calendar endpoint, so the
 * server does the narrowing (location filters resolve through the same
 * targeting logic publishing uses). Applied on "Apply", reset in one
 * click, and reflected in the URL by the workspace hook.
 */
export function FiltersDrawer({
  open,
  onClose,
  value,
  onChange,
}: {
  open: boolean;
  onClose: () => void;
  value: ScheduleFilters;
  onChange: (next: ScheduleFilters) => void;
}) {
  const [draft, setDraft] = useState<ScheduleFilters>(value);
  useEffect(() => {
    if (open) setDraft(value);
  }, [open, value]);

  const tree = useQuery({
    queryKey: ["locations", "tree"],
    queryFn: () => api.get<TreeEntry[]>("/locations/tree"),
    enabled: open,
    staleTime: 5 * 60_000,
  });
  const groups = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<DeviceGroup[]>("/device-groups"),
    enabled: open,
    staleTime: 5 * 60_000,
  });
  const campaigns = useQuery({
    queryKey: ["campaigns", "all"],
    queryFn: () => api.get<CampaignSummary[]>("/campaigns?page_size=100"),
    enabled: open,
    staleTime: 60_000,
  });

  return (
    <Drawer
      title="Filter the schedule"
      open={open}
      onClose={onClose}
      size={400}
      destroyOnHidden
      footer={
        <Space className="w-full justify-end">
          <Button
            onClick={() => {
              setDraft(EMPTY_FILTERS);
              onChange(EMPTY_FILTERS);
              onClose();
            }}
          >
            Reset
          </Button>
          <Button
            type="primary"
            onClick={() => {
              onChange(draft);
              onClose();
            }}
          >
            Apply
          </Button>
        </Space>
      }
    >
      <Form layout="vertical">
        <Form.Item label="Location" extra="Campaigns reaching at least one screen in this location or below.">
          <TreeSelect
            allowClear
            showSearch
            treeDefaultExpandAll
            treeNodeFilterProp="title"
            placeholder="Whole estate"
            loading={tree.isLoading}
            treeData={toTree(tree.data?.data ?? [])}
            value={draft.location_id}
            onChange={(id) => setDraft({ ...draft, location_id: id || undefined })}
            className="w-full"
          />
        </Form.Item>
        <Form.Item label="Device group">
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="Any group"
            loading={groups.isLoading}
            options={(groups.data?.data ?? []).map((g) => ({ value: g.id, label: g.name }))}
            value={draft.group_id}
            onChange={(id) => setDraft({ ...draft, group_id: id || undefined })}
          />
        </Form.Item>
        <Form.Item label="Campaigns">
          <Select
            mode="multiple"
            allowClear
            showSearch
            optionFilterProp="label"
            placeholder="All campaigns"
            loading={campaigns.isLoading}
            maxTagCount="responsive"
            options={(campaigns.data?.data ?? []).map((c) => ({
              value: c.id,
              label: `${c.name} · ${STATUS_LABEL[c.status] ?? c.status}`,
            }))}
            value={draft.campaign_id}
            onChange={(ids) => setDraft({ ...draft, campaign_id: ids })}
          />
        </Form.Item>
        <Form.Item label="Campaign status">
          <Select
            mode="multiple"
            allowClear
            placeholder="Any status"
            maxTagCount="responsive"
            options={Object.entries(STATUS_LABEL)
              .filter(([key]) => key !== "archived")
              .map(([value, label]) => ({ value, label }))}
            value={draft.status}
            onChange={(status) => setDraft({ ...draft, status })}
          />
        </Form.Item>
        <Form.Item label="Priority">
          <Select
            options={PRIORITY_BANDS.map((b) => ({ value: b.value, label: b.label }))}
            value={bandOf(draft)}
            onChange={(band: string) => {
              if (!band) {
                setDraft({ ...draft, priority_min: undefined, priority_max: undefined });
                return;
              }
              const [min, max] = band.split("-").map((n) => Number.parseInt(n, 10));
              setDraft({ ...draft, priority_min: min, priority_max: max });
            }}
          />
        </Form.Item>
        <Form.Item label="Schedule type">
          <Segmented
            block
            value={draft.kind ?? "all"}
            onChange={(v) => setDraft({ ...draft, kind: v === "all" ? undefined : (v as "play" | "blackout") })}
            options={[
              { value: "all", label: "All" },
              { value: "play", label: "Play windows" },
              { value: "blackout", label: "Blackouts" },
            ]}
          />
        </Form.Item>
        <Form.Item label="Conflict status">
          <Space>
            <Switch
              checked={draft.conflicts_only}
              onChange={(on) => setDraft({ ...draft, conflicts_only: on })}
              aria-label="Show only windows with an actionable conflict"
            />
            <Typography.Text>Only windows with an actionable conflict</Typography.Text>
          </Space>
        </Form.Item>
      </Form>
    </Drawer>
  );
}
