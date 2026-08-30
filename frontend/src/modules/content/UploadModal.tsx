import { InboxOutlined } from "@ant-design/icons";
import { Alert, Form, Input, Modal, Upload } from "antd";
import { useState } from "react";
import { api, ApiError } from "../../lib/api";

interface UploadSession {
  upload_session_id: string;
  upload_url: string;
  headers: Record<string, string>;
  asset_id: string;
  version_no: number;
}

interface Props {
  folderId: string | null;
  /** When set, the upload becomes a new version of this asset. */
  assetId?: string;
  onClose: () => void;
  onUploaded: () => void;
}

/** SCR-12 Upload Content: session -> PUT bytes -> complete -> processed. */
export function UploadModal({ folderId, assetId, onClose, onUploaded }: Props) {
  const [form] = Form.useForm<{ name?: string }>();
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<"idle" | "uploading" | "processing">("idle");
  const [error, setError] = useState<string | null>(null);

  async function submit(values: { name?: string }) {
    if (!file) {
      setError("A file is required.");
      return;
    }
    setError(null);
    setPhase("uploading");
    try {
      const endpoint = assetId ? `/assets/${assetId}/versions` : "/assets/uploads";
      const envelope = await api.post<UploadSession>(endpoint, {
        filename: file.name,
        mime_type: file.type || "application/octet-stream",
        size_bytes: file.size,
        folder_id: assetId ? undefined : folderId,
        name: assetId ? undefined : values.name || undefined,
      });
      const session = envelope.data!;

      const put = await fetch(session.upload_url, {
        method: "PUT",
        headers: session.headers,
        body: file,
      });
      if (!put.ok) throw new Error(`Upload failed (${put.status})`);

      setPhase("processing");
      await api.post(`/assets/uploads/${session.upload_session_id}/complete`);
      onUploaded();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : "Upload failed");
      setPhase("idle");
    }
  }

  return (
    <Modal
      title={assetId ? "Upload new version" : "Upload content"}
      open
      onCancel={onClose}
      okText={
        phase === "uploading" ? "Uploading…" : phase === "processing" ? "Processing…" : "Upload"
      }
      okButtonProps={{ disabled: !file }}
      confirmLoading={phase !== "idle"}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
      <Form form={form} layout="vertical" onFinish={submit}>
        <Form.Item label="File" required>
          <Upload.Dragger
            maxCount={1}
            beforeUpload={(f) => {
              setFile(f);
              return false;
            }}
            onRemove={() => setFile(null)}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">Click or drag a file here to upload</p>
          </Upload.Dragger>
        </Form.Item>
        {!assetId && (
          <Form.Item name="name" label="Display name (defaults to filename)">
            <Input />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}
