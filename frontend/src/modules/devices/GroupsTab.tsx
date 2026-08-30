import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { FormField } from "../../components/ui/FormField";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { LocationNode } from "../locations/types";
import type { DeviceGroup } from "./types";

const RULE_FIELDS = ["manufacturer", "platform", "model", "status", "tag", "location"] as const;
const BULK_COMMANDS = ["SYNC_NOW", "RESTART_PLAYER", "RESTART_DEVICE", "CLEAR_CACHE", "SCREENSHOT"];

interface RuleCondition {
  field: (typeof RULE_FIELDS)[number];
  operator: string;
  value: string;
  tagKey?: string;
  tagValue?: string;
}

interface GroupRow extends DeviceGroup {
  group_type: string;
  rule_json: Record<string, unknown> | null;
  member_count: number;
}

/** P2-04 Device Group Builder: static + dynamic rules with preview. */
export function GroupsTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("devices.manage");
  const canControl = hasPermission("devices.control");
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [actionGroup, setActionGroup] = useState<GroupRow | null>(null);
  const [command, setCommand] = useState(BULK_COMMANDS[0]);

  const groupsQuery = useQuery({
    queryKey: ["device-groups"],
    queryFn: () => api.get<GroupRow[]>("/device-groups"),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["device-groups"] });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/device-groups/${id}`),
    onSuccess: invalidate,
    onError: (err) =>
      window.alert(err instanceof ApiError ? err.message : "Failed to delete group"),
  });
  const runAction = useMutation({
    mutationFn: ({ id, command_type }: { id: string; command_type: string }) =>
      api.post<{ queued: number; skipped: number }>(`/device-groups/${id}/actions`, {
        command_type,
      }),
    onSuccess: (envelope) => {
      window.alert(
        `Queued for ${envelope.data!.queued} device(s)` +
          (envelope.data!.skipped ? ` (${envelope.data!.skipped} inactive skipped)` : ""),
      );
      setActionGroup(null);
    },
    onError: (err) =>
      window.alert(err instanceof ApiError ? err.message : "Bulk action failed"),
  });

  if (groupsQuery.isLoading) return <Spinner label="Loading groups…" />;
  const groups = groupsQuery.data?.data ?? [];

  return (
    <div>
      {canManage && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
          >
            Add group
          </button>
        </div>
      )}
      {groups.length === 0 ? (
        <p className="mt-4 rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          No device groups yet. Static groups hold assigned devices; dynamic groups
          match rules like manufacturer or location subtree.
        </p>
      ) : (
        <ul className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {groups.map((group) => (
            <li key={group.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-slate-800">{group.name}</p>
                  <p className="mt-0.5 text-sm text-slate-500">
                    <span
                      className={`mr-2 rounded-full px-2 py-0.5 text-xs font-medium ${
                        group.group_type === "dynamic"
                          ? "bg-sky-100 text-sky-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {group.group_type}
                    </span>
                    {group.member_count} device{group.member_count === 1 ? "" : "s"}
                  </p>
                </div>
                {canManage && (
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm(`Delete group "${group.name}"?`)) remove.mutate(group.id);
                    }}
                    className="text-sm font-medium text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                )}
              </div>
              {canControl && group.member_count > 0 && (
                <button
                  type="button"
                  onClick={() => setActionGroup(group)}
                  className="mt-3 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
                >
                  Bulk action…
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {createOpen && (
        <GroupBuilderModal
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            invalidate();
            setCreateOpen(false);
          }}
        />
      )}
      {actionGroup && (
        <Modal title={`Bulk action: ${actionGroup.name}`} open onClose={() => setActionGroup(null)}>
          <div className="space-y-4">
            <p className="text-sm text-slate-500">
              Queue a remote command for all {actionGroup.member_count} active member
              device(s).
            </p>
            <select
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              aria-label="Command"
              className="block w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {BULK_COMMANDS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setActionGroup(null)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={runAction.isPending}
                onClick={() =>
                  runAction.mutate({ id: actionGroup.id, command_type: command })
                }
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {runAction.isPending ? "Queuing…" : "Queue command"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function GroupBuilderModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [groupType, setGroupType] = useState<"static" | "dynamic">("static");
  const [match, setMatch] = useState<"all" | "any">("all");
  const [conditions, setConditions] = useState<RuleCondition[]>([
    { field: "manufacturer", operator: "eq", value: "" },
  ]);
  const [preview, setPreview] = useState<{ count: number; sample: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const locationsQuery = useQuery({
    queryKey: ["locations-flat"],
    queryFn: () => api.get<LocationNode[]>("/locations?page_size=200"),
    enabled: groupType === "dynamic",
  });

  function buildRule() {
    return {
      match,
      conditions: conditions.map((condition) => ({
        field: condition.field,
        operator: condition.operator,
        value:
          condition.field === "tag"
            ? { key: condition.tagKey ?? "", value: condition.tagValue ?? "" }
            : condition.value,
      })),
    };
  }

  const previewMutation = useMutation({
    mutationFn: () =>
      api.post<{ count: number; sample: string[] }>("/device-groups/preview", {
        rule_json: buildRule(),
      }),
    onSuccess: (envelope) => {
      setPreview(envelope.data!);
      setError(null);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Preview failed"),
  });

  const create = useMutation({
    mutationFn: () =>
      api.post("/device-groups", {
        name,
        group_type: groupType,
        rule_json: groupType === "dynamic" ? buildRule() : null,
      }),
    onSuccess: onCreated,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to create group"),
  });

  function updateCondition(index: number, patch: Partial<RuleCondition>) {
    setConditions((prev) =>
      prev.map((condition, i) => (i === index ? { ...condition, ...patch } : condition)),
    );
    setPreview(null);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    create.mutate();
  }

  return (
    <Modal title="New device group" open onClose={onClose}>
      <form className="space-y-4" onSubmit={onSubmit}>
        <FormField
          id="group-name"
          label="Name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <div className="flex gap-2" role="radiogroup" aria-label="Group type">
          {(["static", "dynamic"] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="radio"
              aria-checked={groupType === t}
              onClick={() => setGroupType(t)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize ${
                groupType === t
                  ? "bg-slate-900 text-white"
                  : "border border-slate-300 text-slate-600"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {groupType === "dynamic" && (
          <div className="space-y-2 rounded-md border border-slate-200 p-3">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              Match
              <select
                value={match}
                onChange={(e) => setMatch(e.target.value as "all" | "any")}
                className="rounded-md border border-slate-300 px-2 py-1"
              >
                <option value="all">all</option>
                <option value="any">any</option>
              </select>
              of the conditions:
            </div>
            {conditions.map((condition, index) => (
              <div key={index} className="flex flex-wrap items-center gap-2 text-sm">
                <select
                  value={condition.field}
                  onChange={(e) =>
                    updateCondition(index, {
                      field: e.target.value as RuleCondition["field"],
                      operator: e.target.value === "location" ? "in_subtree" : "eq",
                      value: "",
                    })
                  }
                  className="rounded-md border border-slate-300 px-2 py-1"
                >
                  {RULE_FIELDS.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
                <select
                  value={condition.operator}
                  onChange={(e) => updateCondition(index, { operator: e.target.value })}
                  className="rounded-md border border-slate-300 px-2 py-1"
                >
                  {(condition.field === "location"
                    ? ["in_subtree", "eq"]
                    : condition.field === "tag"
                      ? ["eq", "ne"]
                      : ["eq", "ne", "contains"]
                  ).map((op) => (
                    <option key={op} value={op}>
                      {op}
                    </option>
                  ))}
                </select>
                {condition.field === "location" ? (
                  <select
                    value={condition.value}
                    onChange={(e) => updateCondition(index, { value: e.target.value })}
                    className="min-w-36 rounded-md border border-slate-300 px-2 py-1"
                  >
                    <option value="">— location —</option>
                    {(locationsQuery.data?.data ?? []).map((loc) => (
                      <option key={loc.id} value={loc.id}>
                        {loc.name}
                      </option>
                    ))}
                  </select>
                ) : condition.field === "tag" ? (
                  <>
                    <input
                      placeholder="key"
                      value={condition.tagKey ?? ""}
                      onChange={(e) => updateCondition(index, { tagKey: e.target.value })}
                      className="w-24 rounded-md border border-slate-300 px-2 py-1"
                    />
                    <input
                      placeholder="value"
                      value={condition.tagValue ?? ""}
                      onChange={(e) => updateCondition(index, { tagValue: e.target.value })}
                      className="w-24 rounded-md border border-slate-300 px-2 py-1"
                    />
                  </>
                ) : (
                  <input
                    placeholder="value"
                    value={condition.value}
                    onChange={(e) => updateCondition(index, { value: e.target.value })}
                    className="w-32 rounded-md border border-slate-300 px-2 py-1"
                  />
                )}
                {conditions.length > 1 && (
                  <button
                    type="button"
                    onClick={() => {
                      setConditions((prev) => prev.filter((_, i) => i !== index));
                      setPreview(null);
                    }}
                    className="text-xs text-red-600 hover:underline"
                  >
                    remove
                  </button>
                )}
              </div>
            ))}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() =>
                  setConditions((prev) => [
                    ...prev,
                    { field: "platform", operator: "eq", value: "" },
                  ])
                }
                className="text-sm font-medium text-slate-600 hover:underline"
              >
                + condition
              </button>
              <button
                type="button"
                onClick={() => previewMutation.mutate()}
                disabled={previewMutation.isPending}
                className="rounded-md border border-slate-300 px-3 py-1 text-sm font-medium text-slate-600 disabled:opacity-50"
              >
                {previewMutation.isPending ? "Previewing…" : "Preview matches"}
              </button>
              {preview && (
                <span className="text-sm text-slate-600">
                  {preview.count} device{preview.count === 1 ? "" : "s"}
                  {preview.sample.length > 0 && (
                    <span className="text-slate-400"> — {preview.sample.join(", ")}</span>
                  )}
                </span>
              )}
            </div>
          </div>
        )}

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
            {create.isPending ? "Creating…" : "Create group"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
