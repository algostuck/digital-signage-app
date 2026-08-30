import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface WhiteLabel {
  custom_domain: string | null;
  domain_verified: boolean;
  email_from_name: string | null;
  email_from_address: string | null;
  region: string;
  branding: { logo_url?: string; primary_color?: string; app_name?: string };
}

/** P3-16 White-Label Settings: theme, custom-domain metadata (verified by
 * the platform admin) and the tenant email sender identity. */
export function WhiteLabelSection() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("organization.manage");
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [form, setForm] = useState({
    custom_domain: "", email_from_name: "", email_from_address: "",
    logo_url: "", primary_color: "#0f172a", app_name: "",
  });

  const query = useQuery({
    queryKey: ["white-label"],
    queryFn: () => api.get<WhiteLabel>("/organization/white-label"),
    retry: false,
  });
  const data = query.data?.data ?? null;

  useEffect(() => {
    if (data) {
      setForm({
        custom_domain: data.custom_domain ?? "",
        email_from_name: data.email_from_name ?? "",
        email_from_address: data.email_from_address ?? "",
        logo_url: data.branding.logo_url ?? "",
        primary_color: data.branding.primary_color ?? "#0f172a",
        app_name: data.branding.app_name ?? "",
      });
    }
  }, [data]);

  const onError = (err: unknown) =>
    setMessage({
      kind: "error",
      text: err instanceof ApiError ? err.message : "Save failed",
    });
  const save = useMutation({
    mutationFn: async () => {
      await api.put("/organization/white-label", {
        custom_domain: form.custom_domain || null,
        email_from_name: form.email_from_name || null,
        email_from_address: form.email_from_address || null,
      });
      await api.patch("/organization", {
        branding_json: {
          logo_url: form.logo_url || null,
          primary_color: form.primary_color,
          app_name: form.app_name || null,
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["white-label"] });
      setMessage({ kind: "ok", text: "White-label settings saved." });
    },
    onError,
  });

  if (!canManage || query.isError || !data) return null;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setMessage(null);
    save.mutate();
  }

  return (
    <div className="mt-8">
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          White label
        </h2>
        <p className="mt-0.5 text-xs text-slate-400">
          Theme + custom-domain metadata (DNS routing and verification are
          handled with the platform administrator) + the sender identity used
          for notification email. Region: {data.region}.
        </p>
        <form className="mt-3 space-y-3" onSubmit={onSubmit}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">
                Custom domain{" "}
                {form.custom_domain && (
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-xs font-medium ${
                      data.domain_verified
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {data.domain_verified ? "verified" : "pending verification"}
                  </span>
                )}
              </span>
              <input
                value={form.custom_domain}
                placeholder="signage.yourcompany.com"
                onChange={(e) => setForm((p) => ({ ...p, custom_domain: e.target.value }))}
                className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Email sender name</span>
              <input
                value={form.email_from_name}
                onChange={(e) =>
                  setForm((p) => ({ ...p, email_from_name: e.target.value }))
                }
                className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Email sender address</span>
              <input
                type="email"
                value={form.email_from_address}
                onChange={(e) =>
                  setForm((p) => ({ ...p, email_from_address: e.target.value }))
                }
                className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Portal name</span>
              <input
                value={form.app_name}
                placeholder="Acme Signage"
                onChange={(e) => setForm((p) => ({ ...p, app_name: e.target.value }))}
                className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Logo URL</span>
              <input
                value={form.logo_url}
                onChange={(e) => setForm((p) => ({ ...p, logo_url: e.target.value }))}
                className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1.5"
              />
            </label>
            <label className="block text-sm">
              <span className="block text-xs text-slate-500">Primary color</span>
              <input
                type="color"
                value={form.primary_color}
                onChange={(e) =>
                  setForm((p) => ({ ...p, primary_color: e.target.value }))
                }
                className="mt-0.5 h-9 w-20 rounded-md border border-slate-300"
              />
            </label>
          </div>
          <button
            type="submit"
            disabled={save.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Save white label
          </button>
        </form>
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
