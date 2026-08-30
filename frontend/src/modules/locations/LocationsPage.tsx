import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Spinner } from "../../components/ui/Spinner";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { LocationFormModal } from "./LocationFormModal";
import { MoveLocationModal } from "./MoveLocationModal";
import { TagEditor } from "./TagEditor";
import type { LocationDetail, TreeEntry } from "./types";

/** SCR-06 Location Tree + SCR-07 Location Details (master-detail). */
export function LocationsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("locations.manage");
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [modal, setModal] = useState<
    | { kind: "create"; parentId: string | null; parentName: string | null }
    | { kind: "edit"; detail: LocationDetail }
    | { kind: "move"; detail: LocationDetail }
    | null
  >(null);

  const treeQuery = useQuery({
    queryKey: ["locations-tree"],
    queryFn: () => api.get<TreeEntry[]>("/locations/tree"),
  });

  const detailQuery = useQuery({
    queryKey: ["location", selectedId],
    queryFn: () => api.get<LocationDetail>(`/locations/${selectedId}`),
    enabled: selectedId != null,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["locations-tree"] });
    queryClient.invalidateQueries({ queryKey: ["location"] });
  };

  const archive = useMutation({
    mutationFn: (id: string) => api.delete(`/locations/${id}`),
    onSuccess: () => {
      invalidate();
      setSelectedId(null);
    },
    onError: (err) =>
      window.alert(err instanceof ApiError ? err.message : "Failed to archive location"),
  });

  function toggleCollapse(id: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const tree = treeQuery.data?.data ?? [];
  const detail = detailQuery.data?.data ?? null;

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Locations</h1>
        {canManage && (
          <button
            type="button"
            onClick={() => setModal({ kind: "create", parentId: null, parentName: null })}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Add root location
          </button>
        )}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(280px,1fr)_2fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          {treeQuery.isLoading ? (
            <Spinner label="Loading tree…" />
          ) : treeQuery.isError ? (
            <p className="p-3 text-sm text-red-600" role="alert">
              Failed to load location tree.
            </p>
          ) : tree.length === 0 ? (
            <p className="p-4 text-sm text-slate-500">
              No locations yet. Create the first root node to start the hierarchy.
            </p>
          ) : (
            <ul role="tree" aria-label="Location hierarchy">
              {tree.map((entry) => (
                <TreeRow
                  key={entry.node.id}
                  entry={entry}
                  selectedId={selectedId}
                  collapsed={collapsed}
                  onSelect={setSelectedId}
                  onToggle={toggleCollapse}
                />
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5">
          {!selectedId ? (
            <p className="p-4 text-sm text-slate-500">
              Select a location to see its details.
            </p>
          ) : detailQuery.isLoading ? (
            <Spinner label="Loading details…" />
          ) : !detail ? (
            <p className="p-4 text-sm text-red-600" role="alert">
              Failed to load location details.
            </p>
          ) : (
            <div>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">
                    {detail.name}
                    {detail.code && (
                      <span className="ml-2 font-mono text-sm text-slate-400">{detail.code}</span>
                    )}
                  </h2>
                  <p className="mt-0.5 text-sm text-slate-500">
                    {detail.type?.name ?? "Untyped"} · depth {detail.depth} ·{" "}
                    <StatusBadge status={detail.status} />
                  </p>
                </div>
                {canManage && (
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        setModal({ kind: "create", parentId: detail.id, parentName: detail.name })
                      }
                      className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white"
                    >
                      Add child
                    </button>
                    <button
                      type="button"
                      onClick={() => setModal({ kind: "edit", detail })}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => setModal({ kind: "move", detail })}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600"
                    >
                      Move
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`Archive "${detail.name}"?`)) archive.mutate(detail.id);
                      }}
                      className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600"
                    >
                      Archive
                    </button>
                  </div>
                )}
              </div>

              <dl className="mt-5 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
                <Item label="Effective timezone" value={detail.effective_timezone} />
                <Item label="Own timezone" value={detail.timezone ?? "inherited"} />
                <Item label="Address" value={detail.address ?? "—"} />
                <Item
                  label="Coordinates"
                  value={
                    detail.latitude != null && detail.longitude != null
                      ? `${detail.latitude}, ${detail.longitude}`
                      : "—"
                  }
                />
                <Item label="Direct children" value={String(detail.children_count)} />
                <Item label="Total descendants" value={String(detail.descendants_count)} />
              </dl>

              <div className="mt-6">
                <TagEditor detail={detail} canManage={canManage} onSaved={invalidate} />
              </div>
            </div>
          )}
        </div>
      </div>

      {modal?.kind === "create" && (
        <LocationFormModal
          parentId={modal.parentId}
          parentName={modal.parentName}
          onClose={() => setModal(null)}
          onSaved={(id) => {
            invalidate();
            setModal(null);
            setSelectedId(id);
          }}
        />
      )}
      {modal?.kind === "edit" && (
        <LocationFormModal
          existing={modal.detail}
          onClose={() => setModal(null)}
          onSaved={() => {
            invalidate();
            setModal(null);
          }}
        />
      )}
      {modal?.kind === "move" && (
        <MoveLocationModal
          detail={modal.detail}
          tree={tree}
          onClose={() => setModal(null)}
          onSaved={() => {
            invalidate();
            setModal(null);
          }}
        />
      )}
    </div>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-slate-700">{value}</dd>
    </div>
  );
}

function TreeRow({
  entry,
  selectedId,
  collapsed,
  onSelect,
  onToggle,
}: {
  entry: TreeEntry;
  selectedId: string | null;
  collapsed: Set<string>;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
}) {
  const { node, children } = entry;
  const isCollapsed = collapsed.has(node.id);
  const isSelected = node.id === selectedId;

  return (
    <li role="treeitem" aria-expanded={children.length ? !isCollapsed : undefined}>
      <div
        className={`flex items-center gap-1 rounded-md px-1 py-1 ${
          isSelected ? "bg-slate-900 text-white" : "hover:bg-slate-100 text-slate-700"
        }`}
        style={{ marginLeft: node.depth * 14 }}
      >
        {children.length > 0 ? (
          <button
            type="button"
            aria-label={isCollapsed ? "Expand" : "Collapse"}
            onClick={() => onToggle(node.id)}
            className={`w-5 text-xs ${isSelected ? "text-slate-300" : "text-slate-400"}`}
          >
            {isCollapsed ? "▸" : "▾"}
          </button>
        ) : (
          <span className="w-5" />
        )}
        <button
          type="button"
          onClick={() => onSelect(node.id)}
          className="flex-1 truncate px-1 py-0.5 text-left text-sm"
        >
          {node.name}
          {node.type && (
            <span className={`ml-2 text-xs ${isSelected ? "text-slate-300" : "text-slate-400"}`}>
              {node.type.name}
            </span>
          )}
        </button>
      </div>
      {!isCollapsed && children.length > 0 && (
        <ul role="group">
          {children.map((child) => (
            <TreeRow
              key={child.node.id}
              entry={child}
              selectedId={selectedId}
              collapsed={collapsed}
              onSelect={onSelect}
              onToggle={onToggle}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
