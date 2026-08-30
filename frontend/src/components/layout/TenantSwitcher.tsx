import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Select } from "antd";
import { useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface Membership {
  organization_id: string;
  organization_name: string;
  is_home: boolean;
  is_owner: boolean;
  role_name: string | null;
}

/** Header dropdown shown only when the user belongs to more than one
 * organization. Switching rotates the token pair server-side. */
export function TenantSwitcher() {
  const { user, switchTenant } = useAuth();
  const queryClient = useQueryClient();
  const [switching, setSwitching] = useState(false);

  const membershipsQuery = useQuery({
    queryKey: ["memberships", user?.id],
    queryFn: () => api.get<Membership[]>("/auth/memberships"),
    enabled: user != null,
    staleTime: 5 * 60 * 1000,
  });

  const memberships = membershipsQuery.data?.data ?? [];
  if (memberships.length < 2 || !user) return null;

  const activeId = user.active_organization_id ?? user.organization_id;

  async function onChange(organizationId: string) {
    if (organizationId === activeId) return;
    setSwitching(true);
    try {
      await switchTenant(organizationId);
      // Everything on screen is tenant-scoped: drop all caches.
      queryClient.clear();
    } finally {
      setSwitching(false);
    }
  }

  return (
    <Select
      value={activeId}
      loading={switching}
      disabled={switching}
      onChange={onChange}
      aria-label="Active organization"
      className="w-48"
      options={memberships.map((m) => ({
        value: m.organization_id,
        label: m.is_home ? m.organization_name : `${m.organization_name} (${m.role_name ?? "guest"})`,
      }))}
    />
  );
}
