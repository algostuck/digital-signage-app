import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface MemberRow {
  user_id: string;
  membership_id?: string;
  email: string;
  full_name: string;
  status: string;
  kind: "home" | "guest";
  is_owner: boolean;
  roles: string[];
}

interface RoleRow {
  id: string;
  name: string;
}

/** Tenant members (SaaS core): home users plus guest memberships — users
 * whose home is another organization but who were granted a role here. */
export function MembersTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("members.manage");
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [email, setEmail] = useState("");
  const [roleId, setRoleId] = useState("");

  const membersQuery = useQuery({
    queryKey: ["org-members"],
    queryFn: () => api.get<MemberRow[]>("/organization/members"),
  });
  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<RoleRow[]>("/roles"),
  });

  const done = (text: string) => {
    queryClient.invalidateQueries({ queryKey: ["org-members"] });
    setMessage({ kind: "ok", text });
  };
  const onError = (err: unknown) =>
    setMessage({
      kind: "error",
      text: err instanceof ApiError ? err.message : "Action failed",
    });

  const addMember = useMutation({
    mutationFn: () =>
      api.post("/organization/members", { email, role_id: roleId, is_owner: false }),
    onSuccess: () => {
      done("Member added.");
      setEmail("");
    },
    onError,
  });
  const removeMember = useMutation({
    mutationFn: (membershipId: string) =>
      api.delete(`/organization/members/${membershipId}`),
    onSuccess: () => done("Member removed."),
    onError,
  });

  const members = membersQuery.data?.data ?? [];
  const roles = rolesQuery.data?.data ?? [];

  function onAdd(e: FormEvent) {
    e.preventDefault();
    setMessage(null);
    addMember.mutate();
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        Home users belong to this organization; guests are users from another
        organization granted a role here.
      </p>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-xs uppercase text-slate-400">
            <th className="py-1.5 pr-4">Email</th>
            <th className="py-1.5 pr-4">Name</th>
            <th className="py-1.5 pr-4">Type</th>
            <th className="py-1.5 pr-4">Roles</th>
            <th className="py-1.5 pr-4">Status</th>
            {canManage && <th className="py-1.5">Actions</th>}
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.user_id} className="border-t border-slate-100">
              <td className="py-2 pr-4">{m.email}</td>
              <td className="py-2 pr-4">{m.full_name}</td>
              <td className="py-2 pr-4">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    m.kind === "home"
                      ? "bg-slate-100 text-slate-600"
                      : "bg-sky-100 text-sky-700"
                  }`}
                >
                  {m.kind}
                </span>
              </td>
              <td className="py-2 pr-4">{m.roles.join(", ") || "—"}</td>
              <td className="py-2 pr-4">{m.status}</td>
              {canManage && (
                <td className="py-2">
                  {m.kind === "guest" && m.membership_id && (
                    <button
                      type="button"
                      onClick={() => removeMember.mutate(m.membership_id!)}
                      className="rounded-md border border-red-300 px-2 py-1 text-xs font-medium text-red-600"
                    >
                      Remove
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      {canManage && (
        <form
          className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
          onSubmit={onAdd}
        >
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Existing user's email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-0.5 w-64 rounded-md border border-slate-300 px-2 py-1.5"
            />
          </label>
          <label className="block text-sm">
            <span className="block text-xs text-slate-500">Role</span>
            <select
              required
              value={roleId}
              onChange={(e) => setRoleId(e.target.value)}
              className="mt-0.5 rounded-md border border-slate-300 px-2 py-1.5"
            >
              <option value="">Select role…</option>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={addMember.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Add member
          </button>
        </form>
      )}

      {message && (
        <p
          role={message.kind === "error" ? "alert" : undefined}
          className={`rounded-md px-3 py-2 text-sm ${
            message.kind === "ok"
              ? "bg-emerald-50 text-emerald-700"
              : "bg-red-50 text-red-700"
          }`}
        >
          {message.text}
        </p>
      )}
    </div>
  );
}
