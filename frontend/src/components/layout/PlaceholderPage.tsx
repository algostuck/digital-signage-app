interface Props {
  title: string;
  milestone: string;
}

/** Route stub for modules whose backend slice is not implemented yet.
 *  Replaced with real screens as each vertical slice lands — never shipped
 *  with mock data. */
export function PlaceholderPage({ title, milestone }: Props) {
  return (
    <div className="flex h-full flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white p-12 text-center">
      <h1 className="text-lg font-semibold text-slate-800">{title}</h1>
      <p className="mt-2 max-w-md text-sm text-slate-500">
        This module is scheduled for milestone {milestone}. It will be built as a
        vertical slice (API first, then UI) — see docs/development-plan.md.
      </p>
    </div>
  );
}
