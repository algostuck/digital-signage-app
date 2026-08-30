import { LeftOutlined, PlusOutlined, RightOutlined, StopOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  App,
  Button,
  Card,
  DatePicker,
  Flex,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  TimePicker,
  Typography,
  type TableProps,
} from "antd";
import type { Dayjs } from "dayjs";
import { useState } from "react";
import { PageHeader } from "../../components/ui/PageHeader";
import { EmptyState, LoadingState } from "../../components/ui/states";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import {
  isoDate,
  minuteLabel,
  WEEKDAYS,
  type CalendarData,
  type CampaignSummary,
  type ConflictOverlap,
  type Schedule,
} from "./types";

function startOfWeek(base: Date): Date {
  const date = new Date(base);
  const day = (date.getDay() + 6) % 7; // Monday = 0
  date.setDate(date.getDate() - day);
  date.setHours(0, 0, 0, 0);
  return date;
}

function addDays(base: Date, days: number): Date {
  const date = new Date(base);
  date.setDate(date.getDate() + days);
  return date;
}

/** SCR-21 / P2-11 Schedule Calendar: week + month views, blackouts,
 * recurrence exceptions, conflict indicators. */
export function SchedulesPage() {
  const { hasPermission } = useAuth();
  const { message } = App.useApp();
  const canManage = hasPermission("schedules.manage");
  const queryClient = useQueryClient();
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const [view, setView] = useState<"week" | "month">("week");
  const [createOpen, setCreateOpen] = useState(false);

  // Month view spans 6 calendar weeks starting from the Monday on/before
  // the 1st; well inside the API's 62-day cap.
  const monthAnchor = new Date(weekStart.getFullYear(), weekStart.getMonth(), 1);
  const rangeStart = view === "week" ? weekStart : startOfWeek(monthAnchor);
  const rangeEnd = addDays(rangeStart, view === "week" ? 6 : 41);
  const calendarQuery = useQuery({
    queryKey: ["calendar", view, isoDate(rangeStart)],
    queryFn: () =>
      api.get<CalendarData>(
        `/schedules/calendar?from=${isoDate(rangeStart)}&to=${isoDate(rangeEnd)}`,
      ),
  });
  const schedulesQuery = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.get<Schedule[]>("/schedules"),
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get<CampaignSummary[]>("/campaigns?page_size=100"),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["calendar"] });
    queryClient.invalidateQueries({ queryKey: ["schedules"] });
    queryClient.invalidateQueries({ queryKey: ["campaigns"] });
  };

  const removeSchedule = useMutation({
    mutationFn: (id: string) => api.delete(`/schedules/${id}`),
    onSuccess: () => {
      refresh();
      message.success("Schedule deleted");
    },
    onError: (err) => message.error(err instanceof ApiError ? err.message : "Delete failed"),
  });

  const calendar = calendarQuery.data?.data ?? null;
  const schedules = schedulesQuery.data?.data ?? [];
  const campaignsById = new Map(
    (campaignsQuery.data?.data ?? []).map((c) => [c.id, c] as const),
  );

  const scheduleColumns: TableProps<Schedule>["columns"] = [
    {
      title: "Campaign",
      render: (_, schedule) => (
        <Space size="small">
          <Typography.Text strong>
            {campaignsById.get(schedule.campaign_id)?.name ?? "…"}
          </Typography.Text>
          {schedule.kind === "blackout" && (
            <Tag icon={<StopOutlined />} color="default">
              Blackout
            </Tag>
          )}
          {schedule.expired && <Tag>Expired</Tag>}
        </Space>
      ),
    },
    { title: "Label", responsive: ["lg"], render: (_, s) => s.name ?? "—" },
    {
      title: "Window",
      render: (_, s) =>
        `${s.start_date ?? "∞"} → ${s.end_date ?? "∞"} · ${s.start_time?.slice(0, 5) ?? "00:00"}–${s.end_time?.slice(0, 5) ?? "24:00"}`,
    },
    {
      title: "Recurrence",
      responsive: ["xl"],
      render: (_, s) => (
        <Space size="small" wrap>
          {s.days_of_week && (
            <Typography.Text type="secondary">
              {s.days_of_week.map((d) => WEEKDAYS[d]).join(" ")}
            </Typography.Text>
          )}
          {s.recurrence_json?.days_of_month && (
            <Typography.Text type="secondary">
              monthly: {s.recurrence_json.days_of_month.join(", ")}
            </Typography.Text>
          )}
          {(s.exception_dates_json?.length ?? 0) > 0 && (
            <Typography.Text type="secondary">
              {s.exception_dates_json!.length} exception
              {s.exception_dates_json!.length === 1 ? "" : "s"}
            </Typography.Text>
          )}
          {s.timezone && <Typography.Text type="secondary">{s.timezone}</Typography.Text>}
        </Space>
      ),
    },
    {
      title: "Priority",
      align: "right",
      width: 90,
      render: (_, s) => s.priority,
    },
    ...(canManage
      ? [
          {
            title: "Actions",
            align: "right" as const,
            width: 100,
            render: (_: unknown, s: Schedule) => (
              <Popconfirm
                title="Delete this schedule?"
                onConfirm={() => removeSchedule.mutate(s.id)}
                okButtonProps={{ danger: true }}
              >
                <Button type="link" danger size="small">
                  Delete
                </Button>
              </Popconfirm>
            ),
          },
        ]
      : []),
  ];

  return (
    <div>
      <PageHeader
        title="Schedule Calendar"
        description="When campaigns play — recurring windows, blackouts, conflict checks."
        actions={
          <Space wrap>
            <Segmented
              value={view}
              onChange={(v) => setView(v as "week" | "month")}
              options={[
                { value: "week", label: "Week" },
                { value: "month", label: "Month" },
              ]}
            />
            <Button
              icon={<LeftOutlined />}
              aria-label="Previous period"
              onClick={() => setWeekStart((w) => addDays(w, view === "week" ? -7 : -28))}
            />
            <Typography.Text type="secondary">
              {isoDate(rangeStart)} — {isoDate(rangeEnd)}
            </Typography.Text>
            <Button
              icon={<RightOutlined />}
              aria-label="Next period"
              onClick={() => setWeekStart((w) => addDays(w, view === "week" ? 7 : 28))}
            />
            {canManage && (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
                New schedule
              </Button>
            )}
          </Space>
        }
      />

      {calendar && calendar.conflict_count > 0 && (
        <Alert
          type="warning"
          showIcon
          className="mb-4"
          message={`${calendar.conflict_count} scheduling conflict${
            calendar.conflict_count === 1 ? "" : "s"
          } in this range`}
          description="Overlapping windows at equal campaign priority. Adjust priorities or times."
          role="alert"
        />
      )}

      {calendarQuery.isLoading ? (
        <LoadingState rows={6} />
      ) : (
        <div className="grid grid-cols-7 gap-2">
          {Array.from({ length: view === "week" ? 7 : 42 }, (_, index) => {
            const day = addDays(rangeStart, index);
            const dayIso = isoDate(day);
            const inMonth = day.getMonth() === monthAnchor.getMonth();
            const events = (calendar?.events ?? [])
              .filter((e) => e.date === dayIso)
              .sort((a, b) => a.start_minute - b.start_minute);
            return (
              <Card
                key={dayIso}
                size="small"
                className={view === "month" && !inMonth ? "opacity-60" : undefined}
                styles={{ body: { padding: 8, minHeight: view === "week" ? 160 : 96 } }}
              >
                <Typography.Text type="secondary" className="text-xs font-semibold uppercase">
                  {WEEKDAYS[index % 7]} <span className="font-normal">{day.getDate()}</span>
                </Typography.Text>
                <Space orientation="vertical" size={4} className="mt-1 w-full">
                  {events.map((event) => (
                    <Tag
                      key={`${event.schedule_id}-${event.date}`}
                      color={
                        event.kind === "blackout"
                          ? "default"
                          : event.conflict
                            ? "error"
                            : "processing"
                      }
                      icon={event.kind === "blackout" ? <StopOutlined /> : undefined}
                      bordered={event.conflict}
                      className="!mr-0 w-full whitespace-normal"
                      title={`${event.campaign_name} · priority ${event.campaign_priority}${
                        event.timezone ? ` · ${event.timezone}` : ""
                      }${event.kind === "blackout" ? " · blackout window" : ""}`}
                    >
                      <span className="font-medium">{event.campaign_name}</span>
                      {view === "week" && (
                        <>
                          <br />
                          {minuteLabel(event.start_minute)}–{minuteLabel(event.end_minute)}
                          {event.overnight ? "↦" : ""}
                        </>
                      )}
                    </Tag>
                  ))}
                </Space>
              </Card>
            );
          })}
        </div>
      )}

      <Typography.Title level={5} className="!mt-6">
        All schedules
      </Typography.Title>
      <Table<Schedule>
        size="middle"
        rowKey="id"
        columns={scheduleColumns}
        dataSource={schedules}
        loading={schedulesQuery.isLoading}
        scroll={{ x: "max-content" }}
        pagination={false}
        locale={{ emptyText: <EmptyState title="No schedules yet" /> }}
      />

      {createOpen && (
        <CreateScheduleModal
          campaigns={campaignsQuery.data?.data ?? []}
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            refresh();
            setCreateOpen(false);
          }}
        />
      )}
    </div>
  );
}

interface ScheduleFormValues {
  campaign_id?: string;
  name?: string;
  kind: "play" | "blackout";
  priority: number;
  date_range?: [Dayjs | null, Dayjs | null] | null;
  start_time?: Dayjs | null;
  end_time?: Dayjs | null;
  month_days?: string;
  exceptions?: string;
  timezone?: string;
}

function CreateScheduleModal({
  campaigns,
  onClose,
  onCreated,
}: {
  campaigns: CampaignSummary[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form] = Form.useForm<ScheduleFormValues>();
  const [days, setDays] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [conflictResult, setConflictResult] = useState<{
    overlaps: ConflictOverlap[];
    conflict_count: number;
  } | null>(null);

  function payload(values: ScheduleFormValues) {
    const parsedMonthDays = (values.month_days ?? "")
      .split(",")
      .map((part) => Number.parseInt(part.trim(), 10))
      .filter((n) => !Number.isNaN(n));
    const parsedExceptions = (values.exceptions ?? "")
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    const [start, end] = values.date_range ?? [null, null];
    return {
      campaign_id: values.campaign_id,
      kind: values.kind,
      start_date: start ? start.format("YYYY-MM-DD") : null,
      end_date: end ? end.format("YYYY-MM-DD") : null,
      start_time: values.start_time ? values.start_time.format("HH:mm") : null,
      end_time: values.end_time ? values.end_time.format("HH:mm") : null,
      days_of_week: days.length ? days : null,
      recurrence_json: parsedMonthDays.length ? { days_of_month: parsedMonthDays } : null,
      exception_dates_json: parsedExceptions.length ? parsedExceptions : null,
      timezone: values.timezone || null,
      priority: values.priority || 50,
    };
  }

  const create = useMutation({
    mutationFn: (values: ScheduleFormValues) =>
      api.post("/schedules", { ...payload(values), name: values.name || null }),
    onSuccess: onCreated,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create schedule"),
  });

  const checkConflicts = useMutation({
    mutationFn: (values: ScheduleFormValues) =>
      api.post<{ overlaps: ConflictOverlap[]; conflict_count: number }>(
        "/schedules/conflicts",
        payload(values),
      ),
    onSuccess: (envelope) => {
      setConflictResult(envelope.data!);
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Conflict check failed"),
  });

  function toggleDay(day: number) {
    setDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort(),
    );
  }

  return (
    <Modal
      title="New schedule"
      open
      width={640}
      onCancel={onClose}
      destroyOnHidden
      footer={
        <Flex justify="flex-end" gap="small">
          <Button onClick={onClose}>Cancel</Button>
          <Button
            loading={checkConflicts.isPending}
            onClick={async () => {
              const values = await form.validateFields();
              checkConflicts.mutate(values);
            }}
          >
            Check conflicts
          </Button>
          <Button type="primary" loading={create.isPending} onClick={() => form.submit()}>
            Create schedule
          </Button>
        </Flex>
      }
    >
      {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
      <Form
        form={form}
        layout="vertical"
        initialValues={{ kind: "play", priority: 50 }}
        onFinish={(values) => {
          setError(null);
          create.mutate(values);
        }}
      >
        <Form.Item
          name="campaign_id"
          label="Campaign"
          rules={[{ required: true, message: "Choose a campaign." }]}
        >
          <Select
            showSearch
            optionFilterProp="label"
            placeholder="— choose —"
            options={campaigns.map((c) => ({ value: c.id, label: `${c.name} (p${c.priority})` }))}
          />
        </Form.Item>
        <Flex gap="middle" wrap>
          <Form.Item name="name" label="Label (optional)" className="min-w-48 flex-1">
            <Input />
          </Form.Item>
          <Form.Item name="kind" label="Kind" className="min-w-48 flex-1">
            <Select
              options={[
                { value: "play", label: "Play window" },
                { value: "blackout", label: "Blackout (suppress campaign)" },
              ]}
            />
          </Form.Item>
          <Form.Item name="priority" label="Priority" className="w-28">
            <InputNumber min={1} max={100} className="w-full" />
          </Form.Item>
        </Flex>
        <Flex gap="middle" wrap>
          <Form.Item name="date_range" label="Date range (empty = open-ended)" className="flex-1">
            <DatePicker.RangePicker allowEmpty={[true, true]} className="w-full" />
          </Form.Item>
        </Flex>
        <Flex gap="middle" wrap>
          <Form.Item name="start_time" label="Daily from" className="flex-1">
            <TimePicker format="HH:mm" className="w-full" />
          </Form.Item>
          <Form.Item name="end_time" label="Daily until" className="flex-1">
            <TimePicker format="HH:mm" className="w-full" />
          </Form.Item>
        </Flex>
        <Form.Item label="Days (empty = every day)">
          <Space size={4} wrap>
            {WEEKDAYS.map((label, index) => (
              <Tag.CheckableTag
                key={label}
                checked={days.includes(index)}
                onChange={() => toggleDay(index)}
              >
                {label}
              </Tag.CheckableTag>
            ))}
          </Space>
        </Form.Item>
        <Form.Item name="month_days" label="Days of month (e.g. 1, 15 — empty = any)">
          <Input placeholder="1, 15" />
        </Form.Item>
        <Form.Item name="exceptions" label="Exception dates (ISO, comma-separated — skipped days)">
          <Input placeholder="2026-12-25, 2027-01-01" />
        </Form.Item>
        <Form.Item name="timezone" label="Timezone (IANA, empty = inherit device/location/org)">
          <Input placeholder="e.g. Asia/Kolkata" />
        </Form.Item>
      </Form>

      {conflictResult && (
        <Alert
          type={conflictResult.conflict_count > 0 ? "error" : "success"}
          showIcon
          message={
            conflictResult.overlaps.length === 0
              ? "No overlaps with other campaigns in the checked range."
              : `${conflictResult.overlaps.length} overlap${
                  conflictResult.overlaps.length === 1 ? "" : "s"
                }${
                  conflictResult.conflict_count > 0
                    ? ` — ${conflictResult.conflict_count} at equal priority`
                    : ""
                }`
          }
          description={
            conflictResult.overlaps.length > 0 && (
              <ul className="mt-1 list-none space-y-0.5 p-0 text-xs">
                {conflictResult.overlaps.slice(0, 5).map((row, index) => (
                  <li key={index}>
                    {row.date} {minuteLabel(row.window[0])}–{minuteLabel(row.window[1])} vs{" "}
                    {row.campaigns
                      .map((c) => c.campaign_name)
                      .filter((n, i, all) => all.indexOf(n) === i)
                      .join(" / ")}{" "}
                    → winner: <strong>{row.winner_campaign_name}</strong>
                    {row.conflict ? " (conflict)" : ""}
                  </li>
                ))}
                {conflictResult.overlaps.length > 5 && (
                  <li>… and {conflictResult.overlaps.length - 5} more</li>
                )}
              </ul>
            )
          }
        />
      )}
    </Modal>
  );
}
