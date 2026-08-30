import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { FormField } from "../../components/ui/FormField";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Permission, Role } from "./types";

export function RolesTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("roles.manage");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Role | "new" | null>(null);

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles"),
  });
  const permissionsQuery = useQuery({
    queryKey: ["permissions"],
    queryFn: () => api.get<Permission[]>("/permissions"),
  });

  const roles = rolesQuery.data?.data ?? [];
  const permissions = permissionsQuery.data?.data ?? [];

  if (rolesQuery.isLoading) return <Spinner label="Loading roles…" />;
  if (rolesQuery.isError)
    return (
      <p className="text-sm text-red-600" role="alert">
        Failed to load roles.
      </p>
    );

  return (
    <div>
      {canManage && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setEditing("new")}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Add role
          </button>
        </div>
      )}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {roles.map((role) => (
          <div key={role.id} className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-medium text-slate-900">
                  {role.name}
                  {role.is_system && (
                    <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
                      System
                    </span>
                  )}
                </h3>
                {role.description && (
                  <p className="mt-1 text-sm text-slate-500">{role.description}</p>
                )}
              </div>
              {canManage && !role.is_system && (
                <button
                  type="button"
                  onClick={() => setEditing(role)}
                  className="text-sm font-medium text-slate-600 hover:underline"
                >
                  Edit
                </button>
              )}
            </div>
            <p className="mt-3 text-xs uppercase tracking-wide text-slate-400">
              {role.permissions.length} permissions
            </p>
            <div className="mt-1 flex flex-wrap gap-1">
              {role.permissions.slice(0, 12).map((p) => (
                <span
                  key={p.code}
                  className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600"
                >
                  {p.code}
                </span>
              ))}
              {role.permissions.length > 12 && (
                <span className="text-xs text-slate-400">
                  +{role.permissions.length - 12} more
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {editing && (
        <RoleModal
          role={editing === "new" ? null : editing}
          permissions={permissions}
          onClose={() => setEditing(null)}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ["roles"] });
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}

function RoleModal({
  role,
  permissions,
  onClose,
  onSaved,
}: {
  role: Role | null;
  permissions: Permission[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [codes, setCodes] = useState<Set<string>>(
    new Set(role?.permissions.map((p) => p.code) ?? []),
  );
  const [error, setError] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const groups = new Map<string, Permission[]>();
    for (const p of permissions) {
      const domain = p.code.split(".")[0];
      groups.set(domain, [...(groups.get(domain) ?? []), p]);
    }
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [permissions]);

  const save = useMutation({
    mutationFn: () => {
      const body = { name, description: description || null, permission_codes: [...codes] };
      return role ? api.patch(`/roles/${role.id}`, body) : api.post("/roles", body);
    },
    onSuccess: onSaved,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to save role"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    save.mutate();
  }

  function toggle(code: string, checked: boolean) {
    setCodes((prev) => {
      const next = new Set(prev);
      if (checked) next.add(code);
      else next.delete(code);
      return next;
    });
  }

  return (
    <Modal title={role ? `Edit role: ${role.name}` : "Add role"} open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <FormField
          id="role-name"
          label="Name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <FormField
          id="role-description"
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <fieldset>
          <legend className="text-sm font-medium text-slate-700">Permissions</legend>
          <div className="mt-2 max-h-64 space-y-3 overflow-y-auto rounded-md border border-slate-200 p-3">
            {grouped.map(([domain, perms]) => (
              <div key={domain}>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {domain}
                </p>
                <div className="mt-1 space-y-1">
                  {perms.map((p) => (
                    <label
                      key={p.code}
                      className="flex items-center gap-2 text-sm text-slate-700"
                      title={p.description ?? undefined}
                    >
                      <input
                        type="checkbox"
                        checked={codes.has(p.code)}
                        onChange={(e) => toggle(p.code, e.target.checked)}
                      />
                      {p.code}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </fieldset>
        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={save.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {save.isPending ? "Saving…" : "Save role"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
