import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../../lib/api";

interface Policy {
  entity_type: string;
  require_approval: boolean;
  maker_checker: boolean;
}

/** P2-APP-001: tenant approval policy controls (part of Tenant Settings). */
export function ApprovalPolicySection({ canManage }: { canManage: boolean }) {
  const queryClient = useQueryClient();
  const policiesQuery = useQuery({
    queryKey: ["approval-policies"],
    queryFn: () => api.get<Policy[]>("/approval-policies"),
    enabled: canManage,
  });

  const save = useMutation({
    mutationFn: (policy: Policy) =>
      api.put(`/approval-policies/${policy.entity_type}`, {
        require_approval: policy.require_approval,
        maker_checker: policy.maker_checker,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["approval-policies"] }),
    onError: (err) =>
      window.alert(err instanceof ApiError ? err.message : "Failed to save policy"),
  });

  if (!canManage) return null;
  const policies = policiesQuery.data?.data ?? [];

  return (
    <section className="mt-6 rounded-lg border border-slate-200 bg-white p-6">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
        Approval policies
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        Govern which submissions need review and whether the submitter may decide
        their own request (maker-checker).
      </p>
      <div className="mt-3 space-y-2">
        {policies.map((policy) => (
          <div
            key={policy.entity_type}
            className="flex flex-wrap items-center gap-4 rounded-md border border-slate-100 px-3 py-2 text-sm"
          >
            <span className="w-24 font-medium capitalize text-slate-800">
              {policy.entity_type}s
            </span>
            <label className="flex items-center gap-2 text-slate-600">
              <input
                type="checkbox"
                checked={policy.require_approval}
                onChange={(e) =>
                  save.mutate({ ...policy, require_approval: e.target.checked })
                }
              />
              Require approval
            </label>
            <label className="flex items-center gap-2 text-slate-600">
              <input
                type="checkbox"
                checked={policy.maker_checker}
                disabled={!policy.require_approval}
                onChange={(e) => save.mutate({ ...policy, maker_checker: e.target.checked })}
              />
              Maker-checker (no self-approval)
            </label>
          </div>
        ))}
      </div>
    </section>
  );
}
