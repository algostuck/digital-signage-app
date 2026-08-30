import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Spinner } from "../../components/ui/Spinner";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface ApiVersionRow {
  version: string;
  lifecycle_state: string;
  sunset_at: string | null;
  released_at: string | null;
  changelog: { date: string; note: string }[];
}

interface OpenApiMeta {
  openapi_url: string | null;
  docs_url: string | null;
  products: { name: string; description: string | null; versions: ApiVersionRow[] }[];
}

interface SandboxInfo {
  organization_id: string;
  name: string;
  code: string;
  enrollment_key: string;
  devices: number;
  created?: boolean;
}

interface SimulatedDevice {
  device_id: string;
  serial_no: string;
  device_token: string;
  heartbeat_url: string;
  manifest_url: string;
}

const LIFECYCLE_STYLE: Record<string, string> = {
  current: "bg-emerald-100 text-emerald-700",
  preview: "bg-sky-100 text-sky-700",
  deprecated: "bg-amber-100 text-amber-700",
  sunset: "bg-red-100 text-red-700",
};

/** P3-23 Developer Portal: versioned contracts + changelog, sandbox tenant,
 * device simulator. API keys stay in Settings → Integrations (2H). */
export function DeveloperPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [simulated, setSimulated] = useState<SimulatedDevice | null>(null);

  const metaQuery = useQuery({
    queryKey: ["developer-openapi"],
    queryFn: () => api.get<OpenApiMeta>("/developer/openapi"),
    retry: false,
  });
  const sandboxQuery = useQuery({
    queryKey: ["developer-sandbox"],
    queryFn: () => api.get<SandboxInfo | null>("/developer/sandbox"),
    retry: false,
    enabled: metaQuery.isSuccess,
  });

  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");
  const provision = useMutation({
    mutationFn: () => api.post<SandboxInfo>("/developer/sandbox", {}),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["developer-sandbox"] });
      queryClient.invalidateQueries({ queryKey: ["memberships"] });
    },
    onError,
  });
  const simulate = useMutation({
    mutationFn: () =>
      api.post<SimulatedDevice>("/developer/sandbox/simulate-device", {}),
    onSuccess: (envelope) => {
      setError(null);
      setSimulated(envelope.data!);
      queryClient.invalidateQueries({ queryKey: ["developer-sandbox"] });
    },
    onError,
  });

  if (!hasPermission("api_keys.manage"))
    return (
      <p className="text-sm text-red-600" role="alert">
        Requires the api_keys.manage permission.
      </p>
    );
  if (metaQuery.isLoading) return <Spinner label="Loading developer portal…" />;
  if (metaQuery.isError)
    return (
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800" role="alert">
        {metaQuery.error instanceof ApiError
          ? metaQuery.error.message
          : "Developer portal unavailable."}
      </p>
    );

  const meta = metaQuery.data?.data;
  const sandbox = sandboxQuery.data?.data ?? null;

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Developer Portal</h1>
        <p className="mt-1 text-sm text-slate-500">
          Versioned API contracts, sandbox tenant and device simulator. API
          keys are managed in Settings → Integrations.
        </p>
        {meta?.docs_url && (
          <p className="mt-2 text-sm">
            Interactive docs:{" "}
            <a
              href={meta.docs_url}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-sky-700 underline"
            >
              {meta.docs_url}
            </a>{" "}
            · OpenAPI:{" "}
            <a
              href={meta.openapi_url ?? "#"}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-sky-700 underline"
            >
              {meta.openapi_url}
            </a>
          </p>
        )}
      </div>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Sandbox tenant
        </h2>
        <p className="mt-0.5 text-xs text-slate-400">
          An isolated test organization — build and break freely without
          touching production content or devices. You get an owner membership,
          so it appears in the tenant switcher in the header.
        </p>
        {sandbox == null ? (
          <button
            type="button"
            disabled={provision.isPending}
            onClick={() => provision.mutate()}
            className="mt-3 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Provision sandbox
          </button>
        ) : (
          <div className="mt-3 space-y-2 text-sm">
            <p>
              <span className="font-medium text-slate-800">{sandbox.name}</span>{" "}
              <span className="font-mono text-xs text-slate-500">({sandbox.code})</span>{" "}
              · {sandbox.devices} device{sandbox.devices === 1 ? "" : "s"}
            </p>
            <p className="text-xs text-slate-500">
              Enrollment key (for player registration):{" "}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono">
                {sandbox.enrollment_key}
              </code>
            </p>
            <button
              type="button"
              disabled={simulate.isPending}
              onClick={() => simulate.mutate()}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Simulate a device
            </button>
            {simulated && (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2">
                <p className="font-medium text-amber-800">
                  Device {simulated.serial_no} enrolled — token shown only once:
                </p>
                <code className="mt-1 block break-all font-mono text-xs text-slate-800">
                  {simulated.device_token}
                </code>
                <p className="mt-1 font-mono text-xs text-slate-500">
                  POST {simulated.heartbeat_url} · GET {simulated.manifest_url}
                  {"  "}(header X-Device-Token)
                </p>
              </div>
            )}
          </div>
        )}
      </section>

      {(meta?.products ?? []).map((product) => (
        <section key={product.name} className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            {product.name}
          </h2>
          {product.description && (
            <p className="mt-0.5 text-xs text-slate-400">{product.description}</p>
          )}
          <div className="mt-3 space-y-3">
            {product.versions.map((v) => (
              <div key={v.version} className="rounded-md border border-slate-200 p-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-slate-800">
                    {v.version}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      LIFECYCLE_STYLE[v.lifecycle_state] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {v.lifecycle_state}
                  </span>
                  {v.sunset_at && (
                    <span className="text-xs text-red-600">
                      sunset {new Date(v.sunset_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <ul className="mt-2 space-y-1 text-sm text-slate-600">
                  {v.changelog.map((entry, i) => (
                    <li key={i}>
                      <span className="font-mono text-xs text-slate-400">{entry.date}</span>{" "}
                      {entry.note}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      ))}

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
