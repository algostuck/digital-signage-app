import {
  DownloadOutlined,
  InboxOutlined,
  RedoOutlined,
  SendOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Flex,
  Image,
  List,
  Popconfirm,
  Space,
  Typography,
} from "antd";
import { ToneTag } from "@/design-system";
import { useState } from "react";
import { LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { UploadModal } from "./UploadModal";
import { formatBytes, type Asset, type AssetVersion } from "./types";

interface Props {
  assetId: string;
  onClose: () => void;
  onChanged: () => void;
}

/** SCR-13 Content Details: preview, metadata, versions, lifecycle. */
export function AssetDetailModal({ assetId, onClose, onChanged }: Props) {
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("content.edit");
  const canDelete = hasPermission("content.delete");
  const queryClient = useQueryClient();
  const [uploadVersion, setUploadVersion] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const assetQuery = useQuery({
    queryKey: ["asset", assetId],
    queryFn: () => api.get<Asset>(`/assets/${assetId}`),
  });
  const versionsQuery = useQuery({
    queryKey: ["asset-versions", assetId],
    queryFn: () => api.get<AssetVersion[]>(`/assets/${assetId}/versions`),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["asset", assetId] });
    queryClient.invalidateQueries({ queryKey: ["asset-versions", assetId] });
    onChanged();
  };

  const action = useMutation({
    mutationFn: (verb: string) => api.post(`/assets/${assetId}/${verb}`),
    onSuccess: refresh,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Action failed"),
  });

  async function download() {
    setError(null);
    try {
      const envelope = await api.get<{ url: string }>(`/assets/${assetId}/download-url`);
      window.open(envelope.data!.url, "_blank");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Download unavailable");
    }
  }

  const asset = assetQuery.data?.data ?? null;
  if (!asset) {
    return (
      <Drawer title="Content details" open onClose={onClose} size={600} placement="right">
        <LoadingState rows={6} />
      </Drawer>
    );
  }

  const version = asset.current_version;

  return (
    <Drawer
      title={asset.name}
      open
      onClose={onClose}
      width={600}
      placement="right"
      footer={
        <Flex wrap justify="flex-end" gap="small">
          <Button icon={<DownloadOutlined />} onClick={download}>
            Download
          </Button>
          {canEdit && (
            <Button icon={<UploadOutlined />} onClick={() => setUploadVersion(true)}>
              New version
            </Button>
          )}
          {canEdit && asset.status === "draft" && (
            <Button type="primary" icon={<SendOutlined />} onClick={() => action.mutate("publish")}>
              Publish
            </Button>
          )}
          {canDelete && asset.status !== "archived" && (
            <Popconfirm
              title={`Archive "${asset.name}"?`}
              onConfirm={() => action.mutate("archive")}
              okButtonProps={{ danger: true }}
            >
              <Button danger icon={<InboxOutlined />}>
                Archive
              </Button>
            </Popconfirm>
          )}
          {canDelete && asset.status === "archived" && (
            <Button icon={<RedoOutlined />} onClick={() => action.mutate("restore")}>
              Restore
            </Button>
          )}
        </Flex>
      }
    >
      <Space orientation="vertical" size="middle" className="w-full">
        <Space size="small" wrap>
          <StatusBadge status={asset.status} />
          <ToneTag tone="default" className="capitalize">
            {asset.type}
          </ToneTag>
          {version && <StatusBadge status={version.processing_status} />}
        </Space>

        {asset.thumbnail_url && (
          <Image
            src={asset.thumbnail_url}
            alt={`Preview of ${asset.name}`}
            height={192}
            className="rounded-md border border-slate-200 object-contain"
          />
        )}

        {version && (
          <Descriptions
            size="small"
            column={{ xs: 1, sm: 2 }}
            items={[
              { label: "File", children: version.original_filename },
              { label: "Size", children: formatBytes(version.size_bytes) },
              {
                label: "Dimensions",
                children:
                  version.width && version.height ? `${version.width}×${version.height}` : "—",
              },
              { label: "Version", children: `v${version.version_no}` },
            ]}
          />
        )}
        {version?.processing_error && (
          <Alert
            type="error"
            showIcon
            message={`Processing failed: ${version.processing_error}`}
          />
        )}

        {asset.tags.length > 0 && (
          <Space size={[4, 8]} wrap>
            {asset.tags.map((t) => (
              <ToneTag tone="default" key={t.id}>
                {t.key}={t.value}
              </ToneTag>
            ))}
          </Space>
        )}

        <div>
          <Typography.Text type="secondary" className="text-xs font-medium uppercase tracking-wide">
            Versions
          </Typography.Text>
          <List
            size="small"
            dataSource={versionsQuery.data?.data ?? []}
            renderItem={(v) => (
              <List.Item className="!px-0 !py-1">
                <Space size="small" wrap>
                  <Typography.Text>
                    v{v.version_no} · {v.original_filename} · {formatBytes(v.size_bytes)}
                  </Typography.Text>
                  <StatusBadge status={v.processing_status} />
                </Space>
              </List.Item>
            )}
          />
        </div>

        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Space>

      {uploadVersion && (
        <UploadModal
          folderId={null}
          assetId={assetId}
          onClose={() => setUploadVersion(false)}
          onUploaded={refresh}
        />
      )}
    </Drawer>
  );
}
