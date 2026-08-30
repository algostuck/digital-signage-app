import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { useAuth } from "./auth";

export interface Entitlements {
  plan_code: string | null;
  plan_name: string | null;
  values: Record<string, boolean | number | null>;
}

/**
 * Tenant plan entitlements for UI gating only (locked/unlocked states,
 * "upgrade to unlock" affordances). Enforcement stays server-side — this
 * hook must never be the only thing standing between a user and an
 * action.
 */
export function useEntitlements() {
  const { user } = useAuth();
  const query = useQuery({
    queryKey: ["entitlements", user?.active_organization_id ?? user?.organization_id],
    queryFn: () => api.get<Entitlements>("/entitlements"),
    enabled: user != null,
    staleTime: 5 * 60 * 1000,
  });

  const data = query.data?.data ?? null;

  /** True when the feature flag is on, or while entitlements are still
   * loading / for legacy orgs without a subscription (fail-open for UI:
   * the server still refuses anything actually locked). */
  function hasFeature(key: string): boolean {
    if (!data) return true;
    const value = data.values[key];
    return value !== false;
  }

  return { entitlements: data, hasFeature, isLoading: query.isLoading };
}
