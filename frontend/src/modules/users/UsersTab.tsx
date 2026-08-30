import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { FormField } from "../../components/ui/FormField";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Role, UserRow } from "./types";

export function UsersTab() {
  const { hasPermission, user: sessionUser } = useAuth();
  const canManage = hasPermission("users.manage");
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRow | null>(null);
  const pageSize = 20;

  const usersQuery = useQuery({
    queryKey: ["users", { search, page }],
    queryFn: () =>
      api.get<UserRow[]>(
        `/users?page=${page}&page_size=${pageSize}${search ? `&q=${encodeURIComponent(search)}` : ""}`,
      ),
  });

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles"),
    enabled: canManage,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  const deactivate = useMutation({
    mutationFn: (id: string) => api.delete(`/users/${id}`),
    onSuccess: invalidate,
  });
  const activate = useMutation({
    mutationFn: (id: string) => api.post(`/users/${id}/activate`),
    onSuccess: invalidate,
  });

  const users = usersQuery.data?.data ?? [];
  const total = usersQuery.data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search by name or email…"
          aria-label="Search users"
          className="w-72 rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
        />
        {canManage && (
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Add user
          </button>
        )}
      </div>

      {usersQuery.isLoading ? (
        <Spinner label="Loading users…" />
      ) : usersQuery.isError ? (
        <p className="mt-6 text-sm text-red-600" role="alert">
          Failed to load users.
        </p>
      ) : users.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          No users match your search.
        </p>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Roles</th>
                <th className="px-4 py-3">Status</th>
                {canManage && <th className="px-4 py-3 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-800">{u.full_name}</td>
                  <td className="px-4 py-3 text-slate-600">{u.email}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {u.roles.map((r) => r.name).join(", ") || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={u.status} />
                  </td>
                  {canManage && (
                    <td className="space-x-3 px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => setEditingUser(u)}
                        className="text-sm font-medium text-slate-600 hover:underline"
                      >
                        Edit
                      </button>
                      {u.id !== sessionUser?.id &&
                        (u.status === "deactivated" ? (
                          <button
                            type="button"
                            onClick={() => activate.mutate(u.id)}
                            className="text-sm font-medium text-emerald-700 hover:underline"
                          >
                            Activate
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              if (window.confirm(`Deactivate ${u.email}?`)) {
                                deactivate.mutate(u.id);
                              }
                            }}
                            className="text-sm font-medium text-red-600 hover:underline"
                          >
                            Deactivate
                          </button>
                        ))}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            Page {page} of {totalPages} · {total} users
          </span>
          <div className="space-x-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-md border border-slate-300 px-3 py-1.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}

      <CreateUserModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        roles={rolesQuery.data?.data ?? []}
        onCreated={invalidate}
      />
      {editingUser && (
        <EditUserModal
          user={editingUser}
          roles={rolesQuery.data?.data ?? []}
          onClose={() => setEditingUser(null)}
          onSaved={() => {
            invalidate();
            setEditingUser(null);
          }}
        />
      )}
    </div>
  );
}

function RoleChecklist({
  roles,
  selected,
  onToggle,
}: {
  roles: Role[];
  selected: string[];
  onToggle: (id: string, checked: boolean) => void;
}) {
  return (
    <fieldset>
      <legend className="text-sm font-medium text-slate-700">Roles</legend>
      <div className="mt-2 max-h-40 space-y-1 overflow-y-auto rounded-md border border-slate-200 p-2">
        {roles.map((role) => (
          <label key={role.id} className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={selected.includes(role.id)}
              onChange={(e) => onToggle(role.id, e.target.checked)}
            />
            {role.name}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function EditUserModal({
  user,
  roles,
  onClose,
  onSaved,
}: {
  user: UserRow;
  roles: Role[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [fullName, setFullName] = useState(user.full_name);
  const [roleIds, setRoleIds] = useState<string[]>(user.roles.map((r) => r.id));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      api.patch(`/users/${user.id}`, { full_name: fullName, role_ids: roleIds }),
    onSuccess: onSaved,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to update user"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    save.mutate();
  }

  return (
    <Modal title={`Edit user: ${user.email}`} open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <FormField
          id="edit-user-name"
          label="Full name"
          required
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
        <RoleChecklist
          roles={roles}
          selected={roleIds}
          onToggle={(id, checked) =>
            setRoleIds((ids) => (checked ? [...ids, id] : ids.filter((i) => i !== id)))
          }
        />
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
            {save.isPending ? "Saving…" : "Save"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function CreateUserModal({
  open,
  onClose,
  roles,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  roles: Role[];
  onCreated: () => void;
}) {
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [roleIds, setRoleIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      api.post("/users", {
        email,
        full_name: fullName,
        password: password || null,
        role_ids: roleIds,
      }),
    onSuccess: () => {
      onCreated();
      onClose();
      setEmail("");
      setFullName("");
      setPassword("");
      setRoleIds([]);
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create user"),
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <Modal title="Add user" open={open} onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <FormField
          id="new-user-email"
          label="Email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <FormField
          id="new-user-name"
          label="Full name"
          required
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
        />
        <FormField
          id="new-user-password"
          label="Password (leave empty to invite)"
          type="password"
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <RoleChecklist
          roles={roles}
          selected={roleIds}
          onToggle={(id, checked) =>
            setRoleIds((ids) => (checked ? [...ids, id] : ids.filter((i) => i !== id)))
          }
        />
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
            disabled={create.isPending}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create user"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
