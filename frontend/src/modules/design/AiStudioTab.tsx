import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface AiOutputRow {
  id: string;
  kind: string;
  content: Record<string, unknown>;
  confidence: number;
  fallback: boolean;
  safety_status: string;
  safety_notes: string | null;
}

interface AiRequestRow {
  id: string;
  operation: string;
  provider: string;
  model_ref: string | null;
  template_version: string | null;
  status: string;
  created_at: string | null;
  outputs: AiOutputRow[];
}

const SAFETY_STYLE: Record<string, string> = {
  passed: "bg-emerald-100 text-emerald-700",
  pending: "bg-sky-100 text-sky-700",
  flagged: "bg-amber-100 text-amber-800",
  rejected: "bg-red-100 text-red-700",
};

const TEXT_TEMPLATES = [
  { value: "headline", label: "Headline (title case, fit)" },
  { value: "shorten", label: "Shorten to length" },
  { value: "cta", label: "Call to action" },
  { value: "tone_formal", label: "Formal tone" },
  { value: "tone_casual", label: "Casual tone" },
];

const LOCALES = ["hi", "bn", "es", "fr", "de"];

const DIMENSIONS = [
  { label: "Landscape 1920×1080", width: 1920, height: 1080 },
  { label: "Portrait 1080×1920", width: 1080, height: 1920 },
  { label: "Banner 3840×720", width: 3840, height: 720 },
  { label: "Square 1080×1080", width: 1080, height: 1080 },
];

function ConfidenceBadge({ output }: { output: AiOutputRow }) {
  const pct = Math.round(output.confidence * 100);
  return (
    <span className="flex flex-wrap items-center gap-1.5 text-xs">
      <span
        className={`rounded-full px-2 py-0.5 font-medium ${
          SAFETY_STYLE[output.safety_status] ?? "bg-slate-100 text-slate-600"
        }`}
      >
        {output.safety_status}
      </span>
      <span
        className={`rounded-full px-2 py-0.5 font-medium ${
          pct >= 80 ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
        }`}
        title="Recommendation confidence (deterministic provider)"
      >
        {pct}% confidence
      </span>
      {output.fallback && (
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-500">
          fallback result
        </span>
      )}
    </span>
  );
}

/** P3-01 AI Content Studio + P3-02 Variant Manager. Every result is a
 * RECOMMENDATION: labeled with provider/model/template version and
 * confidence; guardrail violations are flagged, approval routing goes
 * through the standard Approvals inbox. */
export function AiStudioTab() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<AiRequestRow | null>(null);

  const requestsQuery = useQuery({
    queryKey: ["ai-requests"],
    queryFn: () => api.get<AiRequestRow[]>("/ai/requests?page_size=10"),
    retry: false,
  });

  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "AI request failed");
  const onDone = (envelope: { data?: AiRequestRow | null }) => {
    setError(null);
    setLastResult(envelope.data ?? null);
    queryClient.invalidateQueries({ queryKey: ["ai-requests"] });
  };

  const [textForm, setTextForm] = useState({ template: "headline", text: "", max_chars: "" });
  const generateText = useMutation({
    mutationFn: () =>
      api.post<AiRequestRow>("/ai/generate/text", {
        template: textForm.template,
        text: textForm.text,
        max_chars: textForm.max_chars ? Number(textForm.max_chars) : null,
      }),
    onSuccess: onDone,
    onError,
  });

  const [localizeForm, setLocalizeForm] = useState({ text: "", locale: "es" });
  const localize = useMutation({
    mutationFn: () =>
      api.post<AiRequestRow>("/ai/localize", {
        text: localizeForm.text,
        target_locale: localizeForm.locale,
      }),
    onSuccess: onDone,
    onError,
  });

  const [creativeForm, setCreativeForm] = useState({ headline: "", body: "", dim: 0 });
  const generateCreative = useMutation({
    mutationFn: () =>
      api.post<AiRequestRow>("/ai/generate/creative", {
        headline: creativeForm.headline,
        body: creativeForm.body || null,
        width: DIMENSIONS[creativeForm.dim].width,
        height: DIMENSIONS[creativeForm.dim].height,
      }),
    onSuccess: onDone,
    onError,
  });

  if (requestsQuery.isError)
    return (
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
        {requestsQuery.error instanceof ApiError
          ? requestsQuery.error.message
          : "AI studio unavailable."}
      </p>
    );

  const canCreate = hasPermission("content.create");
  const canCreative = hasPermission("layouts.manage");
  const requests = requestsQuery.data?.data ?? [];

  function submit(e: FormEvent, mutate: () => void) {
    e.preventDefault();
    setError(null);
    mutate();
  }

  return (
    <div className="space-y-6">
      <p className="text-xs text-slate-400">
        Results are <strong>recommendations</strong> from the configured AI
        provider (currently deterministic rules — no external model). Each
        output records provider, template version and confidence; your
        organization's guardrails and approval policy apply.
      </p>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {canCreate && (
          <form
            className="rounded-lg border border-slate-200 bg-white p-4"
            onSubmit={(e) => submit(e, () => generateText.mutate())}
          >
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Copy assistant
            </h2>
            <select
              aria-label="Text template"
              value={textForm.template}
              onChange={(e) => setTextForm((p) => ({ ...p, template: e.target.value }))}
              className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            >
              {TEXT_TEMPLATES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
            <textarea
              required
              value={textForm.text}
              onChange={(e) => setTextForm((p) => ({ ...p, text: e.target.value }))}
              placeholder="Your copy…"
              rows={3}
              className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            />
            <input
              type="number"
              min={8}
              value={textForm.max_chars}
              onChange={(e) => setTextForm((p) => ({ ...p, max_chars: e.target.value }))}
              placeholder="Max characters (optional)"
              className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            />
            <button
              type="submit"
              disabled={generateText.isPending}
              className="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Generate
            </button>
          </form>
        )}

        {canCreate && (
          <form
            className="rounded-lg border border-slate-200 bg-white p-4"
            onSubmit={(e) => submit(e, () => localize.mutate())}
          >
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Localize
            </h2>
            <textarea
              required
              value={localizeForm.text}
              onChange={(e) => setLocalizeForm((p) => ({ ...p, text: e.target.value }))}
              placeholder="Text with {{placeholders}} preserved…"
              rows={3}
              className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            />
            <select
              aria-label="Target locale"
              value={localizeForm.locale}
              onChange={(e) => setLocalizeForm((p) => ({ ...p, locale: e.target.value }))}
              className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            >
              {LOCALES.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={localize.isPending}
              className="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Localize
            </button>
          </form>
        )}

        {canCreative && (
          <form
            className="rounded-lg border border-slate-200 bg-white p-4"
            onSubmit={(e) => submit(e, () => generateCreative.mutate())}
          >
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Creative variant
            </h2>
            <input
              required
              value={creativeForm.headline}
              onChange={(e) => setCreativeForm((p) => ({ ...p, headline: e.target.value }))}
              placeholder="Headline"
              className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            />
            <input
              value={creativeForm.body}
              onChange={(e) => setCreativeForm((p) => ({ ...p, body: e.target.value }))}
              placeholder="Body (optional)"
              className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            />
            <select
              aria-label="Dimensions"
              value={creativeForm.dim}
              onChange={(e) =>
                setCreativeForm((p) => ({ ...p, dim: Number(e.target.value) }))
              }
              className="mt-2 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            >
              {DIMENSIONS.map((d, i) => (
                <option key={d.label} value={i}>
                  {d.label}
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={generateCreative.isPending}
              className="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Generate variant
            </button>
          </form>
        )}
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {lastResult && (
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Latest result
          </h2>
          {lastResult.outputs.map((output) => (
            <div key={output.id} className="mt-2 space-y-2">
              <ConfidenceBadge output={output} />
              <pre className="max-h-48 overflow-auto rounded bg-slate-50 p-3 font-mono text-xs">
                {JSON.stringify(output.content, null, 2)}
              </pre>
              {output.safety_status === "pending" && (
                <p className="text-xs text-sky-700">
                  Awaiting approval — see the Approvals inbox.
                </p>
              )}
              {output.safety_notes && output.safety_status === "flagged" && (
                <p className="text-xs text-amber-700">Guardrail: {output.safety_notes}</p>
              )}
            </div>
          ))}
          <p className="mt-2 text-xs text-slate-400">
            {lastResult.provider} · {lastResult.model_ref} ·{" "}
            {lastResult.template_version}
          </p>
        </section>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Recent AI activity (explainability trail)
        </h2>
        <table className="mt-2 w-full text-left text-sm">
          <thead>
            <tr className="text-xs uppercase text-slate-400">
              <th className="py-1.5 pr-4">Operation</th>
              <th className="py-1.5 pr-4">Template</th>
              <th className="py-1.5 pr-4">Result</th>
              <th className="py-1.5 pr-4">Safety / confidence</th>
              <th className="py-1.5">When</th>
            </tr>
          </thead>
          <tbody>
            {requests.length === 0 && (
              <tr>
                <td colSpan={5} className="py-3 text-sm text-slate-400">
                  No AI activity yet.
                </td>
              </tr>
            )}
            {requests.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 align-top">
                <td className="py-1.5 pr-4">{r.operation}</td>
                <td className="py-1.5 pr-4 font-mono text-xs">{r.template_version}</td>
                <td className="max-w-md truncate py-1.5 pr-4 font-mono text-xs text-slate-500">
                  {r.outputs[0]
                    ? String(
                        r.outputs[0].content.text ?? r.outputs[0].content.headline ?? "",
                      )
                    : "—"}
                </td>
                <td className="py-1.5 pr-4">
                  {r.outputs[0] && <ConfidenceBadge output={r.outputs[0]} />}
                </td>
                <td className="py-1.5 text-xs text-slate-500">
                  {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
