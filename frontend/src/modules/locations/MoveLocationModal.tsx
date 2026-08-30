import { useMutation } from "@tanstack/react-query";
import { Alert, Form, Modal, TreeSelect } from "antd";
import { useMemo, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { LocationDetail, TreeEntry } from "./types";

interface Props {
  detail: LocationDetail;
  tree: TreeEntry[];
  onClose: () => void;
  onSaved: () => void;
}

interface ParentOption {
  value: string;
  title: string;
  disabled?: boolean;
  children?: ParentOption[];
}

/** A node cannot move under itself or anything in its own subtree; the
 * current parent is shown but not selectable. */
function toParentOptions(entries: TreeEntry[], detail: LocationDetail): ParentOption[] {
  const out: ParentOption[] = [];
  for (const { node, children } of entries) {
    if (node.path.startsWith(detail.path)) continue;
    out.push({
      value: node.id,
      title: node.name,
      disabled: node.id === detail.parent_id,
      children: toParentOptions(children, detail),
    });
  }
  return out;
}

export function MoveLocationModal({ detail, tree, onClose, onSaved }: Props) {
  const [newParentId, setNewParentId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const treeData = useMemo(() => toParentOptions(tree, detail), [tree, detail]);

  const move = useMutation({
    mutationFn: () =>
      api.post(`/locations/${detail.id}/move`, { new_parent_id: newParentId || null }),
    onSuccess: onSaved,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to move location"),
  });

  return (
    <Modal
      title={`Move: ${detail.name}`}
      open
      onCancel={onClose}
      okText="Move location"
      confirmLoading={move.isPending}
      onOk={() => {
        setError(null);
        move.mutate();
      }}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
      <Form layout="vertical">
        <Form.Item
          label="New parent"
          extra="The location's own subtree is excluded to prevent cycles."
        >
          <TreeSelect
            className="w-full"
            value={newParentId || undefined}
            onChange={(value?: string) => setNewParentId(value ?? "")}
            treeData={treeData}
            treeDefaultExpandAll
            showSearch
            treeNodeFilterProp="title"
            allowClear
            placeholder="(root, no parent)"
            aria-label="New parent"
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
