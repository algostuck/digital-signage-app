import { CloseOutlined, PlusOutlined } from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import { Button, Input, Space, Tag, Typography } from "antd";
import { useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { LocationDetail } from "./types";

interface Props {
  detail: LocationDetail;
  canManage: boolean;
  onSaved: () => void;
}

/** Inline key=value tag editor with replace-set save semantics. */
export function TagEditor({ detail, canManage, onSaved }: Props) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (tags: { key: string; value: string }[]) =>
      api.post(`/locations/${detail.id}/tags`, { tags }),
    onSuccess: onSaved,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Failed to save tags"),
  });

  function currentTags() {
    return detail.tags.map((t) => ({ key: t.key, value: t.value }));
  }

  function addTag() {
    setError(null);
    const match = draft.match(/^\s*([^=]+?)\s*=\s*(.+?)\s*$/);
    if (!match) {
      setError("Use key=value format, e.g. tier=premium");
      return;
    }
    save.mutate([...currentTags(), { key: match[1], value: match[2] }]);
    setDraft("");
  }

  function removeTag(key: string, value: string) {
    save.mutate(currentTags().filter((t) => !(t.key === key && t.value === value)));
  }

  return (
    <div>
      <Typography.Text type="secondary" className="text-xs font-medium uppercase tracking-wide">
        Tags
      </Typography.Text>
      <div className="mt-2">
        <Space size={[4, 8]} wrap>
          {detail.tags.length === 0 && (
            <Typography.Text type="secondary">No tags</Typography.Text>
          )}
          {detail.tags.map((t) => (
            <Tag
              key={t.id}
              closable={canManage}
              closeIcon={
                canManage ? (
                  <CloseOutlined aria-label={`Remove tag ${t.key}=${t.value}`} />
                ) : undefined
              }
              onClose={(e) => {
                e.preventDefault();
                removeTag(t.key, t.value);
              }}
            >
              {t.key}={t.value}
            </Tag>
          ))}
        </Space>
      </div>
      {canManage && (
        <Space.Compact className="mt-3">
          <Input
            className="w-48"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onPressEnter={addTag}
            placeholder="key=value"
            aria-label="New tag"
          />
          <Button icon={<PlusOutlined />} onClick={addTag} loading={save.isPending}>
            Add tag
          </Button>
        </Space.Compact>
      )}
      {error && (
        <Typography.Paragraph type="danger" role="alert" className="mt-2 text-sm" style={{ marginBottom: 0 }}>
          {error}
        </Typography.Paragraph>
      )}
    </div>
  );
}
