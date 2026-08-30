const STYLES: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  invited: "bg-amber-100 text-amber-700",
  deactivated: "bg-slate-200 text-slate-600",
  online: "bg-emerald-100 text-emerald-700",
  offline: "bg-red-100 text-red-700",
  warning: "bg-amber-100 text-amber-700",
  critical: "bg-red-100 text-red-700",
  pending: "bg-amber-100 text-amber-700",
  rejected: "bg-red-100 text-red-700",
  decommissioned: "bg-slate-200 text-slate-500",
  ready: "bg-emerald-100 text-emerald-700",
  processing: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
  published: "bg-emerald-100 text-emerald-700",
  draft: "bg-slate-100 text-slate-600",
  archived: "bg-slate-200 text-slate-500",
  pending_approval: "bg-amber-100 text-amber-700",
  approved: "bg-sky-100 text-sky-700",
  paused: "bg-amber-100 text-amber-700",
  expired: "bg-slate-200 text-slate-500",
  queued: "bg-slate-100 text-slate-600",
  publishing: "bg-amber-100 text-amber-700",
  partial: "bg-amber-100 text-amber-700",
  cancelled: "bg-slate-200 text-slate-500",
  acknowledged: "bg-emerald-100 text-emerald-700",
};

export function StatusBadge({ status }: { status: string }) {
  const cls = STYLES[status] ?? "bg-slate-100 text-slate-600";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${cls}`}
    >
      {status}
    </span>
  );
}
