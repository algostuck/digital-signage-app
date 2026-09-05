import { InboxOutlined, UploadOutlined } from "@ant-design/icons";
import { Button, Grid, Typography, Upload, type UploadFile, type UploadProps } from "antd";
import { formatBytes } from "../utilities/format";
import { useFeedback } from "../utilities/feedback";

interface UploadAreaProps {
  /** Accepted extensions / MIME types, e.g. ".mp4,.jpg,image/*". */
  accept?: string;
  /** Human list for the hint: "MP4, JPG, PNG". Derived from `accept` when omitted. */
  acceptLabel?: string;
  maxSizeBytes?: number;
  maxCount?: number;
  multiple?: boolean;
  disabled?: boolean;
  /** Called with the files that passed validation. Upload itself stays
   * with the caller (sessions, presigned PUTs); return false from
   * `beforeUpload` semantics is handled here. */
  onFiles: (files: File[]) => void;
  fileList?: UploadFile[];
  onRemove?: UploadProps["onRemove"];
  /** One line above the hint: "Click or drag a file here". */
  prompt?: string;
}

function labelFromAccept(accept?: string): string | undefined {
  if (!accept) return undefined;
  return accept
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => (part.startsWith(".") ? part.slice(1).toUpperCase() : part.replace("/*", " files")))
    .join(", ");
}

/**
 * The one upload surface (docs/design-system/COMPONENT_CATALOGUE.md):
 * Upload.Dragger on desktop, a button below `md`, with limits stated in
 * the hint and enforced before anything is sent, and one wording for
 * refusals. Progress and per-file status are rendered by antd's list.
 */
export function UploadArea({
  accept,
  acceptLabel,
  maxSizeBytes,
  maxCount = 1,
  multiple = false,
  disabled,
  onFiles,
  fileList,
  onRemove,
  prompt,
}: UploadAreaProps) {
  const { toast } = useFeedback();
  const screens = Grid.useBreakpoint();
  const compact = screens.md === false;

  const hintParts = [acceptLabel ?? labelFromAccept(accept), maxSizeBytes ? `up to ${formatBytes(maxSizeBytes)}` : null].filter(
    Boolean,
  );
  const hint = hintParts.length ? hintParts.join(" · ") : undefined;

  const props: UploadProps = {
    accept,
    multiple,
    maxCount,
    disabled,
    fileList,
    onRemove,
    beforeUpload: (file, batch) => {
      if (maxSizeBytes && file.size > maxSizeBytes) {
        toast.error(`${file.name} is ${formatBytes(file.size)}; the limit is ${formatBytes(maxSizeBytes)}.`);
        return Upload.LIST_IGNORE;
      }
      // Hand the whole batch over once, on its last file.
      if (batch[batch.length - 1] === file) {
        const accepted = batch.filter((f) => !maxSizeBytes || f.size <= maxSizeBytes);
        onFiles(accepted);
      }
      return false;
    },
  };

  if (compact) {
    return (
      <Upload {...props}>
        <Button icon={<UploadOutlined />} disabled={disabled}>
          {prompt ?? "Choose file"}
        </Button>
        {hint && (
          <Typography.Text type="secondary" style={{ display: "block", marginTop: 4, fontSize: 12 }}>
            {hint}
          </Typography.Text>
        )}
      </Upload>
    );
  }

  return (
    <Upload.Dragger {...props}>
      <p className="ant-upload-drag-icon">
        <InboxOutlined />
      </p>
      <p className="ant-upload-text">{prompt ?? (multiple ? "Click or drag files here" : "Click or drag a file here")}</p>
      {hint && <p className="ant-upload-hint">{hint}</p>}
    </Upload.Dragger>
  );
}
