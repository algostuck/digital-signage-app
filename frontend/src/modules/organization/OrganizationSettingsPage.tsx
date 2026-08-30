import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { FormField } from "../../components/ui/FormField";
import { Spinner } from "../../components/ui/Spinner";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { ApprovalPolicySection } from "./ApprovalPolicySection";
import { IntegrationsSection } from "./IntegrationsSection";
import { PlanBillingSection } from "./PlanBillingSection";
import { QuotasRetentionSection } from "./QuotasRetentionSection";

interface Organization {
  id: string;
  name: string;
  code: string;
  status: string;
  timezone: string;
  locale: string;
  branding_json: Record<string, unknown> | null;
  quotas_json: Record<string, unknown> | null;
}

/** SCR-03 Organizations / Tenant Settings. */
export function OrganizationSettingsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("organization.manage");
  const queryClient = useQueryClient();

  const orgQuery = useQuery({
    queryKey: ["organization"],
    queryFn: () => api.get<Organization>("/organization"),
  });

  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState("");
  const [locale, setLocale] = useState("");
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const org = orgQuery.data?.data ?? null;
  useEffect(() => {
    if (org) {
      setName(org.name);
      setTimezone(org.timezone);
      setLocale(org.locale);
    }
  }, [org]);

  const save = useMutation({
    mutationFn: () => api.patch("/organization", { name, timezone, locale }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization"] });
      setMessage({ kind: "ok", text: "Organization settings saved." });
    },
    onError: (err) =>
      setMessage({
        kind: "error",
        text: err instanceof ApiError ? err.message : "Failed to save settings",
      }),
  });

  if (orgQuery.isLoading) return <Spinner label="Loading organization…" />;
  if (orgQuery.isError || !org)
    return (
      <p className="text-sm text-red-600" role="alert">
        Failed to load organization.
      </p>
    );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setMessage(null);
    save.mutate();
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-xl font-semibold text-slate-900">Organization Settings</h1>
      <p className="mt-1 text-sm text-slate-500">
        Tenant <span className="font-mono">{org.code}</span> · status {org.status}
      </p>
      <form className="mt-6 space-y-4 rounded-lg border border-slate-200 bg-white p-6" onSubmit={onSubmit}>
        <FormField
          id="org-name"
          label="Organization name"
          required
          disabled={!canManage}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <FormField
          id="org-timezone"
          label="Timezone (IANA, e.g. Asia/Kolkata)"
          required
          disabled={!canManage}
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
        />
        <FormField
          id="org-locale"
          label="Default locale"
          required
          disabled={!canManage}
          value={locale}
          onChange={(e) => setLocale(e.target.value)}
        />
        {message && (
          <p
            role="alert"
            className={`rounded-md px-3 py-2 text-sm ${
              message.kind === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
            }`}
          >
            {message.text}
          </p>
        )}
        {canManage && (
          <button
            type="submit"
            disabled={save.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {save.isPending ? "Saving…" : "Save settings"}
          </button>
        )}
      </form>
      <PlanBillingSection />
      <ApprovalPolicySection canManage={canManage} />
      <QuotasRetentionSection />
      <IntegrationsSection />
    </div>
  );
}
