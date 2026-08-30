import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface SsoProvider {
  id: string;
  issuer: string;
  client_id: string;
  client_secret_ref: string;
  claim_mapping: Record<string, unknown>;
  active: boolean;
  endpoints: Record<string, string> | null;
}

/** P3-17 Enterprise SSO (OIDC): provider config with secrets by env-var
 * reference, claim mapping, discovery test and the tenant login URL. */
export function SsoSection() {
  const { hasPermission, user } = useAuth();
  const canManage = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [form, setForm] = useState({
    issuer: "", client_id: "", client_secret_ref: "", mapping: "", active: false,
  });

  const providerQuery = useQuery({
    queryKey: ["sso-provider"],
    queryFn: () => api.get<SsoProvider | null>("/sso/providers"),
    enabled: canManage,
    retry: false,
  });
  const provider = providerQuery.data?.data ?? null;

  useEffect(() => {
    if (provider) {
      setForm({
        issuer: provider.issuer,
        client_id: provider.client_id,
        client_secret_ref: provider.client_secret_ref,
        mapping: JSON.stringify(provider.claim_mapping, null, 2),
        active: provider.active,
      });
    }
  }, [provider]);

  const onError = (err: unknown) =>
    setMessage({
      kind: "error",
      text: err instanceof ApiError ? err.message : "Action failed",
    });
  const save = useMutation({
    mutationFn: () =>
      api.post("/sso/providers", {
        issuer: form.issuer,
        client_id: form.client_id,
        client_secret_ref: form.client_secret_ref,
        claim_mapping: form.mapping ? JSON.parse(form.mapping) : null,
        active: form.active,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sso-provider"] });
      setMessage({ kind: "ok", text: "SSO provider saved." });
    },
    onError,
  });
  const test = useMutation({
    mutationFn: () => api.post<{ ok: boolean; error?: string }>("/sso/providers/test", {}),
    onSuccess: (envelope) => {
      queryClient.invalidateQueries({ queryKey: ["sso-provider"] });
      const data = envelope.data!;
      setMessage(
        data.ok
          ? { kind: "ok", text: "Issuer discovery succeeded — endpoints cached." }
          : { kind: "error", text: `Discovery failed: ${data.error}` },
      );
    },
    onError,
  });

  if (!canManage) return null;
  if (providerQuery.isError) return null; // entitlement off → section absent

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setMessage(null);
    try {
      if (form.mapping) JSON.parse(form.mapping);
    } catch {
      setMessage({ kind: "error", text: "Claim mapping must be valid JSON" });
      return;
    }
    save.mutate();
  }

  return (
    <div className="mt-8">
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Enterprise SSO (OIDC)
        </h2>
        <p className="mt-0.5 text-xs text-slate-400">
          The IdP authenticates; roles stay platform-managed via claim
          mapping. The client secret is referenced by an environment-variable
          NAME — never stored here.
        </p>
        <form className="mt-3 space-y-3" onSubmit={onSubmit}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {(
              [
                ["issuer", "Issuer (https)", "https://login.example.com"],
                ["client_id", "Client ID", ""],
                ["client_secret_ref", "Client secret env-var NAME", "SSO_CLIENT_SECRET"],
              ] as const
            ).map(([key, label, placeholder]) => (
              <label key={key} className="block text-sm">
                <span className="block text-xs text-slate-500">{label}</span>
                <input
                  required
                  value={form[key]}
                  placeholder={placeholder}
                  onChange={(e) => setForm((p) => ({ ...p, [key]: e.target.value }))}
                  className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
                />
              </label>
            ))}
          </div>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">
              Claim mapping (JSON — email/name/groups paths, role_map,
              auto_provision, default_role)
            </span>
            <textarea
              value={form.mapping}
              onChange={(e) => setForm((p) => ({ ...p, mapping: e.target.value }))}
              rows={5}
              placeholder='{"email": "email", "role_map": {"idp-group": "Organization Administrator"}, "auto_provision": false}'
              className="mt-0.5 w-full rounded-md border border-slate-300 p-2 font-mono text-xs"
            />
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-1.5 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => setForm((p) => ({ ...p, active: e.target.checked }))}
              />
              SSO enabled
            </label>
            <button
              type="submit"
              disabled={save.isPending}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Save provider
            </button>
            {provider && (
              <button
                type="button"
                disabled={test.isPending}
                onClick={() => test.mutate()}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-600 disabled:opacity-50"
              >
                Test connection
              </button>
            )}
          </div>
        </form>
        {provider?.active && user && (
          <p className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-xs text-slate-500">
            SSO entry point:{" "}
            <code className="font-mono">
              GET /api/v1/auth/sso/&lt;org-code&gt;/login?redirect_uri=&lt;portal-callback&gt;
            </code>
          </p>
        )}
        {message && (
          <p
            role={message.kind === "error" ? "alert" : undefined}
            className={`mt-3 rounded-md px-3 py-2 text-sm ${
              message.kind === "ok"
                ? "bg-emerald-50 text-emerald-700"
                : "bg-red-50 text-red-700"
            }`}
          >
            {message.text}
          </p>
        )}
      </section>
    </div>
  );
}
