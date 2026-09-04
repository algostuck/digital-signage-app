import { useQuery, useQueryClient } from "@tanstack/react-query";
import { App } from "antd";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type {
  InvoiceRow,
  PlanRequestRow,
  PlanRow,
  PlatformInvoiceRow,
  TenantDetail,
  TenantQuotas,
  TenantRow,
  TenantSubscription,
} from "./types";

/** One key namespace so any platform mutation can invalidate everything
 * under "platform" without knowing which pages are mounted. */
export const platformKeys = {
  all: ["platform"] as const,
  tenants: ["platform", "tenants"] as const,
  tenant: (id: string) => ["platform", "tenant", id] as const,
  tenantQuotas: (id: string) => ["platform", "tenant", id, "quotas"] as const,
  tenantSubscription: (id: string) => ["platform", "tenant", id, "subscription"] as const,
  tenantInvoices: (id: string) => ["platform", "tenant", id, "invoices"] as const,
  plans: ["platform", "plans"] as const,
  catalogue: ["platform", "entitlement-catalogue"] as const,
  planRequests: (status: string) => ["platform", "plan-requests", status] as const,
  invoices: (status: string | null, tenantId: string | null) =>
    ["platform", "invoices", status ?? "all", tenantId ?? "all"] as const,
};

function superuser(): boolean {
  // Hook-free helper for `enabled` flags; pages are already behind PlatformGuard.
  return true;
}

export function useTenants() {
  const { user } = useAuth();
  return useQuery({
    queryKey: platformKeys.tenants,
    queryFn: () => api.get<TenantRow[]>("/platform/tenants"),
    enabled: !!user?.is_superuser && superuser(),
  });
}

export function useTenant(id: string | undefined) {
  return useQuery({
    queryKey: platformKeys.tenant(id ?? ""),
    queryFn: () => api.get<TenantDetail>(`/platform/tenants/${id}`),
    enabled: !!id,
  });
}

export function useTenantQuotas(id: string | undefined) {
  return useQuery({
    queryKey: platformKeys.tenantQuotas(id ?? ""),
    queryFn: () => api.get<TenantQuotas>(`/platform/tenants/${id}/quotas`),
    enabled: !!id,
  });
}

export function useTenantSubscription(id: string | undefined) {
  return useQuery({
    queryKey: platformKeys.tenantSubscription(id ?? ""),
    queryFn: () => api.get<TenantSubscription>(`/platform/tenants/${id}/subscription`),
    enabled: !!id,
  });
}

export function useTenantInvoices(id: string | undefined) {
  return useQuery({
    queryKey: platformKeys.tenantInvoices(id ?? ""),
    queryFn: () => api.get<InvoiceRow[]>(`/platform/tenants/${id}/invoices`),
    enabled: !!id,
  });
}

export function usePlans() {
  return useQuery({
    queryKey: platformKeys.plans,
    queryFn: () => api.get<PlanRow[]>("/platform/plans"),
  });
}

export function useEntitlementCatalogue() {
  return useQuery({
    queryKey: platformKeys.catalogue,
    queryFn: () => api.get<Record<string, "int" | "bool">>("/platform/entitlements"),
    staleTime: 10 * 60 * 1000,
  });
}

export function usePlanRequests(status: string) {
  return useQuery({
    queryKey: platformKeys.planRequests(status),
    queryFn: () =>
      api.get<PlanRequestRow[]>(`/platform/plan-requests?status=${encodeURIComponent(status)}`),
  });
}

export function usePlatformInvoices(status: string | null, tenantId: string | null) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (tenantId) params.set("tenant_id", tenantId);
  const qs = params.toString();
  return useQuery({
    queryKey: platformKeys.invoices(status, tenantId),
    queryFn: () => api.get<PlatformInvoiceRow[]>(`/platform/invoices${qs ? `?${qs}` : ""}`),
  });
}

/** Success toast + cache invalidation + uniform error toast. Every
 * platform mutation reports through this so feedback is consistent. */
export function usePlatformFeedback() {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  return {
    done(text: string) {
      void queryClient.invalidateQueries({ queryKey: platformKeys.all });
      // Tenant-facing plan lists cache under "plans"; keep them honest too.
      void queryClient.invalidateQueries({ queryKey: ["plans"] });
      message.success(text);
    },
    onError(err: unknown) {
      message.error(err instanceof ApiError ? err.message : "The action could not be completed.");
    },
  };
}

export function formatMoney(amount: string | number, currency: string): string {
  const value = Number(amount);
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency}`;
  }
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function isOverdue(invoice: { status: string; due_at: string | null }): boolean {
  return invoice.status === "issued" && !!invoice.due_at && new Date(invoice.due_at) < new Date();
}

/** IANA zones from the browser when available; a sensible short list
 * otherwise so the select is never empty. */
export function timezoneOptions(): { value: string; label: string }[] {
  const intl = Intl as unknown as { supportedValuesOf?: (key: string) => string[] };
  const zones = intl.supportedValuesOf?.("timeZone") ?? [
    "UTC",
    "Asia/Kolkata",
    "Asia/Dubai",
    "Asia/Singapore",
    "Europe/London",
    "Europe/Berlin",
    "America/New_York",
    "America/Los_Angeles",
    "Australia/Sydney",
  ];
  return zones.map((z) => ({ value: z, label: z.replace(/_/g, " ") }));
}
