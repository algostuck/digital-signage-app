import {
  CalendarOutlined,
  FilterOutlined,
  LeftOutlined,
  LockOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  RetweetOutlined,
  RightOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Badge, Button, Col, Collapse, Grid, Modal, Popconfirm, Row, Segmented, Space, Spin, Typography, type TableProps } from "antd";
import { useCallback, useMemo, useState, type ReactNode } from "react";
import { PageHeader } from "@/design-system";
import { DataTable } from "@/design-system";
import { ErrorState, LoadingState } from "@/design-system";
import { ToneTag } from "@/design-system";
import { api, ApiError } from "../../../lib/api";
import { useAuth } from "../../../lib/auth";
import { CampaignDetailModal } from "../CampaignDetailModal";
import type { CalendarEvent, CampaignSummary, Schedule, ScheduleConflict } from "../types";
import { WEEKDAYS } from "../types";
import { ConflictsDrawer } from "./ConflictsDrawer";
import { addDays, daysBetween, formatDayShort, formatRangeLabel, startOfWeek, windowLabel, type ViewMode } from "./dates";
import { DayPanel } from "./DayPanel";
import { EventChip, EventPopover, type EventActions } from "./EventChip";
import { FiltersDrawer } from "./FiltersDrawer";
import { HealthPanel, SummaryStrip } from "./HealthPanel";
import { MobileAgenda } from "./MobileAgenda";
import { MonthView } from "./MonthView";
import { SEVERITY_LABEL, severityTone, statusLabel } from "./palette";
import { ScheduleFormModal, type SchedulePrefill } from "./ScheduleFormModal";
import { TimeGrid, type MoveProposal } from "./TimeGrid";
import { activeFilterCount, CALENDAR_QUERY_KEY, useScheduleWorkspace } from "./useScheduleWorkspace";

const { useBreakpoint } = Grid;

interface FormState {
  schedule?: Schedule;
  prefill?: SchedulePrefill;
}

interface MoveCheck {
  proposal: MoveProposal;
  schedule: Schedule;
  conflicts: ScheduleConflict[] | null;
  error: string | null;
}

/**
 * The Scheduling Command Center (docs/SCHEDULE_UX_AUDIT.md §8): one
 * calendar contract, three views, filters that the server applies, a
 * health panel with an actionable conflict list, the selected day beside
 * the calendar, and every write confirmed against the conflict dry-run.
 */
export function ScheduleWorkspace() {
  const { hasPermission } = useAuth();
  const { message } = App.useApp();
  const canManage = hasPermission("schedules.manage");
  const queryClient = useQueryClient();
  const screens = useBreakpoint();
  const isMobile = screens.md === false;
  const ws = useScheduleWorkspace();

  const [filtersOpen, setFiltersOpen] = useState(false);
  const [conflictsOpen, setConflictsOpen] = useState(false);
  const [focusConflict, setFocusConflict] = useState<string | null>(null);
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [formState, setFormState] = useState<FormState | null>(null);
  const [moveCheck, setMoveCheck] = useState<MoveCheck | null>(null);

  const schedulesQuery = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.get<Schedule[]>("/schedules"),
    staleTime: 30_000,
  });
  const campaignsQuery = useQuery({
    queryKey: ["campaigns", "all"],
    queryFn: () => api.get<CampaignSummary[]>("/campaigns?page_size=100"),
    staleTime: 60_000,
  });
  const schedulesById = useMemo(
    () => new Map((schedulesQuery.data?.data ?? []).map((s) => [s.id, s] as const)),
    [schedulesQuery.data],
  );
  const campaignsById = useMemo(
    () => new Map((campaignsQuery.data?.data ?? []).map((c) => [c.id, c] as const)),
    [campaignsQuery.data],
  );

  const refresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: [CALENDAR_QUERY_KEY] });
    queryClient.invalidateQueries({ queryKey: ["schedules"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  }, [queryClient]);

  const removeSchedule = useMutation({
    mutationFn: (id: string) => api.delete(`/schedules/${id}`),
    onSuccess: () => {
      refresh();
      message.success("Schedule window deleted");
    },
    onError: (err) => message.error(err instanceof ApiError ? err.message : "Delete failed"),
  });

  const patchSchedule = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) => api.patch(`/schedules/${id}`, body),
    onSuccess: () => {
      refresh();
      setMoveCheck(null);
      message.success("Window moved");
    },
    onError: (err) => message.error(err instanceof ApiError ? err.message : "Could not move the window"),
  });

  /** Drag-and-drop: dry-run the proposal, show the verdict, persist on confirm. */
  const startMove = useCallback(
    async (proposal: MoveProposal) => {
      const schedule = schedulesById.get(proposal.event.schedule_id);
      if (!schedule) {
        message.warning("Reload the page to move this window.");
        return;
      }
      const shift = daysBetween(proposal.event.date, proposal.date).length - 1;
      const direction = proposal.date >= proposal.event.date ? 1 : -1;
      const body = {
        campaign_id: schedule.campaign_id,
        kind: schedule.kind,
        start_date: schedule.start_date ? addDays(schedule.start_date, shift * direction) : null,
        end_date: schedule.end_date ? addDays(schedule.end_date, shift * direction) : null,
        start_time: windowLabel(proposal.start_minute, proposal.start_minute).split("–")[0],
        end_time: proposal.end_minute >= 1440 ? "00:00" : windowLabel(proposal.end_minute, proposal.end_minute).split("–")[0],
        days_of_week: schedule.days_of_week,
        recurrence_json: schedule.recurrence_json,
        exception_dates_json: schedule.exception_dates_json,
        timezone: schedule.timezone,
        priority: schedule.priority,
      };
      setMoveCheck({ proposal, schedule, conflicts: null, error: null });
      try {
        const result = await api.post<{ conflicts?: ScheduleConflict[] }>("/schedules/conflicts", {
          ...body,
          schedule_id: schedule.id,
        });
        setMoveCheck({ proposal, schedule, conflicts: result.data?.conflicts ?? [], error: null });
      } catch (err) {
        setMoveCheck({
          proposal,
          schedule,
          conflicts: [],
          error: err instanceof ApiError ? err.message : "Conflict check failed",
        });
      }
    },
    [message, schedulesById],
  );

  const confirmMove = () => {
    if (!moveCheck) return;
    const { proposal, schedule } = moveCheck;
    const shift = daysBetween(proposal.event.date, proposal.date).length - 1;
    const direction = proposal.date >= proposal.event.date ? 1 : -1;
    patchSchedule.mutate({
      id: schedule.id,
      body: {
        start_date: schedule.start_date ? addDays(schedule.start_date, shift * direction) : null,
        end_date: schedule.end_date ? addDays(schedule.end_date, shift * direction) : null,
        start_time: windowLabel(proposal.start_minute, proposal.start_minute).split("–")[0],
        end_time: proposal.end_minute >= 1440 ? "00:00" : windowLabel(proposal.end_minute, proposal.end_minute).split("–")[0],
      },
    });
  };

  const actions: EventActions = useMemo(
    () => ({
      onOpenCampaign: (id) => setCampaignId(id),
      onEdit: canManage
        ? (event) => {
            const schedule = schedulesById.get(event.schedule_id);
            if (schedule) setFormState({ schedule });
            else message.warning("Reload the page to edit this window.");
          }
        : undefined,
      onDelete: canManage ? (event) => removeSchedule.mutate(event.schedule_id) : undefined,
      onShowConflict: (conflict) => {
        setFocusConflict(conflict.id);
        setConflictsOpen(true);
      },
    }),
    [canManage, message, removeSchedule, schedulesById],
  );

  const conflictsOf = useCallback(
    (event: CalendarEvent) =>
      event.conflict_ids.map((id) => ws.conflictsById.get(id)).filter((c): c is ScheduleConflict => !!c),
    [ws.conflictsById],
  );

  const renderChip = useCallback(
    (event: CalendarEvent, compact = false): ReactNode => (
      <EventPopover event={event} conflicts={conflictsOf(event)} actions={actions} canManage={canManage}>
        <EventChip
          event={event}
          compact={compact}
          selected={event.date === ws.selectedDate && !compact}
          onClick={() => ws.setSelectedDate(event.date)}
        />
      </EventPopover>
    ),
    [actions, canManage, conflictsOf, ws],
  );
  const renderBlock = useCallback(
    (event: CalendarEvent, button: ReactNode) => (
      <EventPopover event={event} conflicts={conflictsOf(event)} actions={actions} canManage={canManage}>
        {button}
      </EventPopover>
    ),
    [actions, canManage, conflictsOf],
  );

  const days = useMemo(() => daysBetween(ws.range.from, ws.range.to), [ws.range.from, ws.range.to]);
  const mobileDays = useMemo(() => {
    const from = startOfWeek(ws.anchor);
    return daysBetween(from, addDays(from, 20));
  }, [ws.anchor]);
  const filterCount = activeFilterCount(ws.filters);
  const loading = ws.calendarQuery.isLoading;
  const fetching = ws.calendarQuery.isFetching && !loading;

  const showOnCalendar = (conflict: ScheduleConflict) => {
    setConflictsOpen(false);
    ws.setView("week");
    ws.setAnchor(conflict.dates.first);
  };

  const selectedEvents = ws.eventsByDate.get(ws.selectedDate) ?? [];

  const scheduleColumns: TableProps<Schedule>["columns"] = [
    {
      title: "Campaign",
      render: (_, s) => (
        <Space size="small" wrap>
          <Button type="link" size="small" className="!h-auto !p-0" onClick={() => setCampaignId(s.campaign_id)}>
            {campaignsById.get(s.campaign_id)?.name ?? "…"}
          </Button>
          {s.kind === "blackout" && (
            <ToneTag tone="default" icon={<LockOutlined />} className="!mr-0">
              Blackout
            </ToneTag>
          )}
          {s.expired && <ToneTag tone="default" className="!mr-0">Ended</ToneTag>}
        </Space>
      ),
    },
    { title: "Label", responsive: ["lg"], render: (_, s) => s.name ?? "—" },
    {
      title: "Dates",
      render: (_, s) => `${s.start_date ? formatDayShort(s.start_date) : "open"} → ${s.end_date ? formatDayShort(s.end_date) : "open"}`,
    },
    {
      title: "Daily",
      render: (_, s) => `${s.start_time?.slice(0, 5) ?? "00:00"}–${s.end_time?.slice(0, 5) ?? "24:00"}`,
    },
    {
      title: "Repeats",
      responsive: ["xl"],
      render: (_, s) => (
        <Typography.Text type="secondary" className="text-xs">
          {s.days_of_week ? s.days_of_week.map((d) => WEEKDAYS[d]).join(" ") : "Every day"}
          {s.recurrence_json?.days_of_month ? ` · monthly ${s.recurrence_json.days_of_month.join(", ")}` : ""}
          {s.exception_dates_json?.length ? ` · ${s.exception_dates_json.length} skipped` : ""}
          {s.timezone ? ` · ${s.timezone}` : ""}
        </Typography.Text>
      ),
    },
    { title: "Priority", align: "right", width: 90, render: (_, s) => s.priority },
    ...(canManage
      ? [
          {
            title: "Actions",
            align: "right" as const,
            width: 140,
            render: (_: unknown, s: Schedule) => (
              <Space size={0}>
                <Button type="link" size="small" onClick={() => setFormState({ schedule: s })}>
                  Edit
                </Button>
                <Popconfirm
                  title="Delete this schedule window?"
                  onConfirm={() => removeSchedule.mutate(s.id)}
                  okButtonProps={{ danger: true }}
                >
                  <Button type="link" danger size="small">
                    Delete
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]
      : []),
  ];

  return (
    <div data-testid="schedule-workspace">
      <PageHeader
        title="Schedule"
        description={`Campaign play windows and blackouts across the estate · times in ${ws.timezone}`}
        actions={
          <Space wrap size="small">
            <Space.Compact>
              <Button icon={<LeftOutlined />} aria-label="Previous period" onClick={() => ws.step(-1)} />
              <Button onClick={ws.goToday} aria-label="Go to today">
                Today
              </Button>
              <Button icon={<RightOutlined />} aria-label="Next period" onClick={() => ws.step(1)} />
            </Space.Compact>
            <Typography.Text strong className="whitespace-nowrap" aria-live="polite">
              {formatRangeLabel(ws.view, ws.anchor)}
            </Typography.Text>
            {!isMobile && (
              <Segmented
                value={ws.view}
                onChange={(v) => ws.setView(v as ViewMode)}
                aria-label="Calendar view"
                options={[
                  { value: "day", label: "Day" },
                  { value: "week", label: "Week" },
                  { value: "month", label: "Month" },
                ]}
              />
            )}
            <Badge count={filterCount} size="small" offset={[-4, 4]}>
              <Button icon={<FilterOutlined />} onClick={() => setFiltersOpen(true)} aria-label={`Filters${filterCount ? `, ${filterCount} active` : ""}`}>
                Filters
              </Button>
            </Badge>
            {canManage && (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setFormState({ prefill: { date: ws.selectedDate } })}>
                Schedule campaign
              </Button>
            )}
          </Space>
        }
      />

      <SummaryStrip calendar={ws.calendar} loading={loading} />
      <HealthPanel
        calendar={ws.calendar}
        loading={loading}
        onReview={() => {
          setFocusConflict(null);
          setConflictsOpen(true);
        }}
        showingOnlyConflicts={ws.filters.conflicts_only}
        onShowOnlyConflicts={(on) => ws.setFilters({ ...ws.filters, conflicts_only: on })}
      />

      {ws.calendarQuery.isError ? (
        <ErrorState
          title="The schedule could not be loaded"
          description={ws.calendarQuery.error instanceof ApiError ? ws.calendarQuery.error.message : undefined}
          onRetry={() => ws.calendarQuery.refetch()}
        />
      ) : loading ? (
        <LoadingState rows={8} />
      ) : isMobile ? (
        <MobileAgenda
          days={mobileDays}
          selectedDate={ws.selectedDate}
          today={ws.today}
          nowMinute={ws.nowMinute}
          timezone={ws.timezone}
          eventsByDate={ws.eventsByDate}
          onSelectDate={(iso) => {
            ws.setSelectedDate(iso);
            if (!mobileDays.includes(iso)) ws.setAnchor(iso);
          }}
          renderChip={(event) => renderChip(event, false)}
        />
      ) : (
        <Spin spinning={fetching} delay={200}>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={15} xl={15}>
              {ws.view === "month" ? (
                <MonthView
                  anchor={ws.anchor}
                  selectedDate={ws.selectedDate}
                  today={ws.today}
                  eventsByDate={ws.eventsByDate}
                  onSelectDate={(iso) => {
                    ws.setSelectedDate(iso);
                    if (iso.slice(0, 7) !== ws.anchor.slice(0, 7)) ws.setAnchor(iso);
                  }}
                  renderChip={renderChip}
                />
              ) : (
                <TimeGrid
                  days={days}
                  eventsByDate={ws.eventsByDate}
                  today={ws.today}
                  nowMinute={ws.nowMinute}
                  selectedDate={ws.selectedDate}
                  onSelectDate={ws.setSelectedDate}
                  canManage={canManage}
                  onSlotClick={
                    canManage
                      ? (iso, minute) =>
                          setFormState({
                            prefill: { date: iso, start_minute: minute, end_minute: Math.min(minute + 60, 1440) },
                          })
                      : undefined
                  }
                  onMove={canManage ? startMove : undefined}
                  renderBlock={renderBlock}
                  renderChip={(event) => renderChip(event, false)}
                />
              )}
              <Legend />
            </Col>
            <Col xs={24} lg={9} xl={9}>
              <DayPanel
                date={ws.selectedDate}
                today={ws.today}
                nowMinute={ws.nowMinute}
                timezone={ws.timezone}
                events={selectedEvents}
                renderChip={(event) => renderChip(event, false)}
              />
            </Col>
          </Row>
        </Spin>
      )}

      <Collapse
        className="mt-6"
        items={[
          {
            key: "all",
            label: `All schedule windows (${schedulesQuery.data?.data?.length ?? 0})`,
            children: (
              <DataTable<Schedule>
                rowKey="id"
                columns={scheduleColumns}
                dataSource={schedulesQuery.data?.data ?? []}
                loading={schedulesQuery.isLoading}
                pagination={{ pageSize: 20, hideOnSinglePage: true }}
              />
            ),
          },
        ]}
      />

      <FiltersDrawer open={filtersOpen} onClose={() => setFiltersOpen(false)} value={ws.filters} onChange={ws.setFilters} />
      <ConflictsDrawer
        open={conflictsOpen}
        onClose={() => setConflictsOpen(false)}
        conflicts={ws.calendar?.conflicts ?? []}
        focusId={focusConflict}
        onOpenCampaign={(id) => setCampaignId(id)}
        onShowOnCalendar={showOnCalendar}
      />
      {campaignId && (
        <CampaignDetailModal campaignId={campaignId} onClose={() => setCampaignId(null)} onChanged={refresh} />
      )}
      {formState && (
        <ScheduleFormModal
          schedule={formState.schedule}
          prefill={formState.prefill}
          campaigns={campaignsQuery.data?.data ?? []}
          onClose={() => setFormState(null)}
          onSaved={() => {
            setFormState(null);
            refresh();
            message.success(formState.schedule ? "Schedule window updated" : "Schedule window created");
          }}
        />
      )}
      <Modal
        title="Move this window?"
        open={!!moveCheck}
        onCancel={() => setMoveCheck(null)}
        onOk={confirmMove}
        okText="Move window"
        okButtonProps={{ loading: patchSchedule.isPending, disabled: !moveCheck || moveCheck.conflicts === null }}
        destroyOnHidden
      >
        {moveCheck && (
          <div>
            <Typography.Paragraph className="!mb-2">
              <strong>{moveCheck.proposal.event.campaign_name}</strong>
              {moveCheck.schedule.name ? ` · ${moveCheck.schedule.name}` : ""}
            </Typography.Paragraph>
            <Typography.Paragraph className="!mb-2">
              {formatDayShort(moveCheck.proposal.event.date)}{" "}
              {windowLabel(moveCheck.proposal.event.start_minute, moveCheck.proposal.event.end_minute)} →{" "}
              <strong>
                {formatDayShort(moveCheck.proposal.date)}{" "}
                {windowLabel(moveCheck.proposal.start_minute, moveCheck.proposal.end_minute)}
              </strong>
            </Typography.Paragraph>
            <Typography.Text type="secondary" className="block text-xs">
              This changes the daily window
              {moveCheck.proposal.date !== moveCheck.proposal.event.date ? " and shifts the date range" : ""} for
              every occurrence of this schedule.
            </Typography.Text>
            <div className="mt-3">
              {moveCheck.conflicts === null ? (
                <Space>
                  <Spin size="small" /> Checking conflicts…
                </Space>
              ) : moveCheck.error ? (
                <Typography.Text type="danger">{moveCheck.error}</Typography.Text>
              ) : moveCheck.conflicts.length === 0 ? (
                <ToneTag tone="success">No conflicts on shared screens</ToneTag>
              ) : (
                <ul className="m-0 list-none space-y-1 p-0 text-sm">
                  {moveCheck.conflicts.map((c) => (
                    <li key={c.id} className="flex flex-wrap items-center gap-1.5">
                      <ToneTag tone={severityTone(c.severity)} className="!mr-0">
                        {SEVERITY_LABEL[c.severity]}
                      </ToneTag>
                      <span>
                        {c.campaigns.find((x) => x.schedule_id !== "proposed")?.campaign_name} ·{" "}
                        {windowLabel(c.window[0], c.window[1])} · {c.dates.count} day{c.dates.count === 1 ? "" : "s"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function Legend() {
  return (
    <Typography.Text type="secondary" className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs" aria-label="Legend">
      <span>
        <CalendarOutlined aria-hidden /> Colour = campaign
      </span>
      <span>
        <LockOutlined aria-hidden /> Striped = blackout
      </span>
      <span>
        <WarningOutlined aria-hidden /> Dashed outline = conflict
      </span>
      <span>
        <RetweetOutlined aria-hidden /> Recurring
      </span>
      <span>
        <PlayCircleOutlined aria-hidden /> Playing now
      </span>
      <span>Draft, pending and paused campaigns are shown; only published ones can be “playing”. {statusLabel("expired")} windows are dimmed.</span>
    </Typography.Text>
  );
}
