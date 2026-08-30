import { Button, DatePicker, Space, Typography } from "antd";
import type { Dayjs } from "dayjs";
import { useState } from "react";
import { ApiError } from "../../lib/api";
import type { Device } from "../devices/types";
import { TVPreviewModal } from "./TVPreviewModal";
import { useDevicePreviewSource } from "./usePreviewSource";

/** "What is this screen showing?" — and, with a time chosen, "what will it
 * show then?". Both answers come from the server's own resolver, so the
 * preview cannot drift from what the device actually plays. */
export function DeviceTVPreview({
  device,
  open,
  onClose,
}: {
  device: Device | null;
  open: boolean;
  onClose(): void;
}) {
  const [at, setAt] = useState<Dayjs | null>(null);
  const { source, query } = useDevicePreviewSource(
    device,
    at ? at.toISOString() : null,
    open,
  );

  const toolbar = (
    <Space wrap align="center">
      <Typography.Text type="secondary">Preview as of</Typography.Text>
      <DatePicker
        showTime={{ format: "HH:mm" }}
        format="YYYY-MM-DD HH:mm"
        value={at}
        onChange={setAt}
        placeholder="Now"
        aria-label="Preview at a specific date and time"
      />
      {at && <Button onClick={() => setAt(null)}>Back to now</Button>}
      {device?.timezone && (
        <Typography.Text type="secondary">Device timezone {device.timezone}</Typography.Text>
      )}
    </Space>
  );

  return (
    <TVPreviewModal
      open={open}
      onClose={onClose}
      title={device ? `TV preview — ${device.name}` : "TV preview"}
      source={source}
      loading={query.isPending}
      error={
        query.error
          ? query.error instanceof ApiError
            ? query.error.message
            : "Could not load the preview manifest"
          : null
      }
      onRetry={() => void query.refetch()}
      toolbar={toolbar}
    />
  );
}
