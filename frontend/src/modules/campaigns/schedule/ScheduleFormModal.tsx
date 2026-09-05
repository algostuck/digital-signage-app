import { useMutation } from "@tanstack/react-query";
import {
  Alert,
  Button,
  DatePicker,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Tag,
  TimePicker,
  Typography,
} from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useState } from "react";
import { timeZoneOptions, ToneTag } from "@/design-system";
import { EntityList } from "@/design-system";
import { api, ApiError } from "../../../lib/api";
import type { CampaignSummary, ConflictOverlap, Schedule, ScheduleConflict } from "../types";
import { WEEKDAYS } from "../types";
import { formatDayShort, minuteLabel, timeToMinute, windowLabel } from "./dates";
import { REASON_LABEL, SEVERITY_LABEL, severityTone } from "./palette";

export interface SchedulePrefill {
  campaign_id?: string;
  date?: string;
  start_minute?: number;
  end_minute?: number;
}

interface FormValues {
  campaign_id?: string;
  name?: string;
  kind: "play" | "blackout";
  priority: number;
  date_range?: [Dayjs | null, Dayjs | null] | null;
  start_time?: Dayjs | null;
  end_time?: Dayjs | null;
  month_days?: number[];
  exceptions?: Dayjs[];
  timezone?: string;
}

interface DryRun {
  overlaps: ConflictOverlap[];
  conflict_count: number;
  conflicts?: ScheduleConflict[];
  actionable_count?: number;
}

function minuteToDayjs(minute: number): Dayjs {
  return dayjs().hour(Math.floor(minute / 60) % 24).minute(minute % 60).second(0).millisecond(0);
}

/**
 * Create or edit a schedule window with proper controls (pickers instead
 * of comma-separated text), an inline conflict dry-run graded by the same
 * engine as the calendar, and prefill from a clicked slot.
 */
export function ScheduleFormModal({
  schedule,
  prefill,
  campaigns,
  onClose,
  onSaved,
}: {
  /** Present when editing; absent when creating. */
  schedule?: Schedule;
  prefill?: SchedulePrefill;
  campaigns: CampaignSummary[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const editing = !!schedule;
  const [form] = Form.useForm<FormValues>();
  const [days, setDays] = useState<number[]>(schedule?.days_of_week ?? []);
  const [error, setError] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState<DryRun | null>(null);

  const initialValues: FormValues = schedule
    ? {
        campaign_id: schedule.campaign_id,
        name: schedule.name ?? undefined,
        kind: schedule.kind,
        priority: schedule.priority,
        date_range: [
          schedule.start_date ? dayjs(schedule.start_date) : null,
          schedule.end_date ? dayjs(schedule.end_date) : null,
        ],
        start_time: schedule.start_time ? minuteToDayjs(timeToMinute(schedule.start_time, 0)) : null,
        end_time: schedule.end_time ? minuteToDayjs(timeToMinute(schedule.end_time, 0)) : null,
        month_days: schedule.recurrence_json?.days_of_month ?? [],
        exceptions: (schedule.exception_dates_json ?? []).map((d) => dayjs(d)),
        timezone: schedule.timezone ?? undefined,
      }
    : {
        campaign_id: prefill?.campaign_id,
        kind: "play",
        priority: 50,
        date_range: prefill?.date ? [dayjs(prefill.date), dayjs(prefill.date)] : null,
        start_time: prefill?.start_minute !== undefined ? minuteToDayjs(prefill.start_minute) : null,
        end_time: prefill?.end_minute !== undefined ? minuteToDayjs(prefill.end_minute) : null,
        month_days: [],
        exceptions: [],
        timezone: "Asia/Kolkata",
      };

  function payload(values: FormValues) {
    const [start, end] = values.date_range ?? [null, null];
    return {
      campaign_id: values.campaign_id,
      name: values.name || null,
      kind: values.kind,
      start_date: start ? start.format("YYYY-MM-DD") : null,
      end_date: end ? end.format("YYYY-MM-DD") : null,
      start_time: values.start_time ? values.start_time.format("HH:mm") : null,
      end_time: values.end_time ? values.end_time.format("HH:mm") : null,
      days_of_week: days.length ? days : null,
      recurrence_json: values.month_days?.length ? { days_of_month: values.month_days } : null,
      exception_dates_json: values.exceptions?.length ? values.exceptions.map((d) => d.format("YYYY-MM-DD")) : null,
      timezone: values.timezone || null,
      priority: values.priority || 50,
    };
  }

  const save = useMutation({
    mutationFn: (values: FormValues) =>
      editing ? api.patch(`/schedules/${schedule.id}`, payload(values)) : api.post("/schedules", payload(values)),
    onSuccess: onSaved,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to save the schedule"),
  });

  const check = useMutation({
    mutationFn: (values: FormValues) =>
      api.post<DryRun>("/schedules/conflicts", {
        ...payload(values),
        schedule_id: schedule?.id ?? null,
      }),
    onSuccess: (envelope) => {
      setDryRun(envelope.data!);
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Conflict check failed"),
  });

  const toggleDay = (day: number) =>
    setDays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort()));

  const conflicts = dryRun?.conflicts ?? [];
  const actionable = dryRun?.actionable_count ?? conflicts.filter((c) => c.severity !== "low").length;

  return (
    <Modal
      title={editing ? "Edit schedule window" : "Schedule a campaign"}
      open
      width={680}
      onCancel={onClose}
      destroyOnHidden
      footer={
        <Flex justify="flex-end" gap="small" wrap>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            loading={check.isPending}
            onClick={async () => {
              const values = await form.validateFields();
              check.mutate(values);
            }}
          >
            Check conflicts
          </Button>
          <Button type="primary" loading={save.isPending} onClick={() => form.submit()}>
            {editing ? "Save changes" : "Create window"}
          </Button>
        </Flex>
      }
    >
      {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
      <Form<FormValues>
        form={form}
        layout="vertical"
        initialValues={initialValues}
        onFinish={(values) => {
          setError(null);
          save.mutate(values);
        }}
      >
        <Form.Item name="campaign_id" label="Campaign" rules={[{ required: true, message: "Choose a campaign." }]}>
          <Select
            showSearch
            disabled={editing}
            optionFilterProp="label"
            placeholder="Choose a campaign"
            options={campaigns.map((c) => ({ value: c.id, label: `${c.name} · priority ${c.priority}` }))}
          />
        </Form.Item>
        <Flex gap="middle" wrap>
          <Form.Item name="name" label="Label (optional)" className="min-w-48 flex-1">
            <Input placeholder="e.g. Evening — Diwali" maxLength={120} />
          </Form.Item>
          <Form.Item name="kind" label="Type" className="min-w-48 flex-1">
            <Select
              options={[
                { value: "play", label: "Play window" },
                { value: "blackout", label: "Blackout (suppress the campaign)" },
              ]}
            />
          </Form.Item>
          <Form.Item name="priority" label="Window priority" className="w-32" tooltip="Tie-break between this campaign's own windows.">
            <InputNumber min={1} max={100} className="w-full" />
          </Form.Item>
        </Flex>
        <Form.Item name="date_range" label="Dates (leave empty for open-ended)">
          <DatePicker.RangePicker allowEmpty={[true, true]} className="w-full" format="D MMM YYYY" />
        </Form.Item>
        <Flex gap="middle" wrap>
          <Form.Item name="start_time" label="Daily from" className="flex-1">
            <TimePicker format="HH:mm" minuteStep={5} className="w-full" needConfirm={false} />
          </Form.Item>
          <Form.Item name="end_time" label="Daily until" className="flex-1" extra="An end before the start wraps past midnight.">
            <TimePicker format="HH:mm" minuteStep={5} className="w-full" needConfirm={false} />
          </Form.Item>
        </Flex>
        <Form.Item label="Days of the week (none = every day)">
          <Space size={4} wrap role="group" aria-label="Days of the week">
            {WEEKDAYS.map((label, index) => (
              <Tag.CheckableTag key={label} checked={days.includes(index)} onChange={() => toggleDay(index)}>
                {label}
              </Tag.CheckableTag>
            ))}
          </Space>
        </Form.Item>
        <Flex gap="middle" wrap>
          <Form.Item name="month_days" label="Days of the month (none = any)" className="min-w-56 flex-1">
            <Select
              mode="multiple"
              allowClear
              maxTagCount="responsive"
              placeholder="e.g. 1st and 15th"
              options={Array.from({ length: 31 }, (_, i) => ({ value: i + 1, label: String(i + 1) }))}
            />
          </Form.Item>
          <Form.Item name="exceptions" label="Skip these dates" className="min-w-56 flex-1">
            <DatePicker multiple className="w-full" format="D MMM YYYY" maxTagCount="responsive" />
          </Form.Item>
        </Flex>
        <Form.Item name="timezone" label="Timezone" extra="Leave empty to inherit the screen → location → organisation zone.">
          <Select showSearch allowClear placeholder="Inherit" options={timeZoneOptions()} />
        </Form.Item>
      </Form>

      {dryRun && (
        <div data-testid="dry-run-result">
          <Alert
            type={actionable > 0 ? "warning" : "success"}
            showIcon
            message={
              conflicts.length === 0
                ? dryRun.overlaps.length === 0
                  ? "No overlaps with other campaigns in the checked range."
                  : `${dryRun.overlaps.length} time overlap${dryRun.overlaps.length === 1 ? "" : "s"}, none on shared screens — nothing to resolve.`
                : `${actionable} conflict${actionable === 1 ? "" : "s"} to resolve${
                    conflicts.length > actionable ? ` (${conflicts.length - actionable} informational)` : ""
                  }`
            }
          />
          {conflicts.length > 0 && (
            <EntityList
              dense
              style={{ marginTop: 8 }}
              items={conflicts}
              rowKey="id"
              renderItem={(c) => {
                const other = c.campaigns.find((x) => x.schedule_id !== "proposed") ?? c.campaigns[1];
                return (
                    <Space size={6} wrap>
                      <ToneTag tone={severityTone(c.severity)} className="!mr-0">
                        {SEVERITY_LABEL[c.severity]}
                      </ToneTag>
                      <Typography.Text>{REASON_LABEL[c.reason]}</Typography.Text>
                      <Typography.Text type="secondary" className="text-xs">
                        {other?.campaign_name} · {windowLabel(c.window[0], c.window[1])} ·{" "}
                        {c.dates.count === 1
                          ? formatDayShort(c.dates.first)
                          : `${c.dates.count} days from ${formatDayShort(c.dates.first)}`}{" "}
                        · {c.screens_affected.count} screen{c.screens_affected.count === 1 ? "" : "s"}
                      </Typography.Text>
                    </Space>
                );
              }}
            />
          )}
          {conflicts.length === 0 && dryRun.overlaps.length > 0 && (
            <Typography.Text type="secondary" className="mt-1 block text-xs">
              First overlap: {dryRun.overlaps[0].date} {minuteLabel(dryRun.overlaps[0].window[0])}–
              {minuteLabel(dryRun.overlaps[0].window[1])} with{" "}
              {dryRun.overlaps[0].campaigns.map((c) => c.campaign_name).join(" / ")} · winner{" "}
              {dryRun.overlaps[0].winner_campaign_name}.
            </Typography.Text>
          )}
        </div>
      )}
    </Modal>
  );
}
