import { DeleteOutlined, FolderAddOutlined, FolderOutlined, UploadOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  Col,
  Input,
  Menu,
  Modal,
  Pagination,
  Popconfirm,
  Row,
  Select,
  Typography,
} from "antd";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { FilterBar } from "@/design-system";
import { SearchBar } from "@/design-system";
import { PageContainer } from "@/design-system";
import { EmptyState, LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { AssetDetailModal } from "./AssetDetailModal";
import { UploadModal } from "./UploadModal";
import { formatBytes, type Asset, type Folder } from "./types";

const TYPE_FILTERS = ["", "image", "video", "audio", "document", "html", "text", "data"];
const STATUS_FILTERS = ["", "draft", "published", "archived"];

/** SCR-11 Content Library: folders, filters, grid, lifecycle. */
export function ContentPage() {
  const { hasPermission } = useAuth();
  const { message } = App.useApp();
  const canCreate = hasPermission("content.create");
  const canDelete = hasPermission("content.delete");
  const queryClient = useQueryClient();

  const [folderId, setFolderId] = useState<string | null>(null);
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const [typeFilter, setTypeFilter] = useState(searchParams.get("type") ?? "");
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") ?? "");
  const [page, setPage] = useState(1);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [newFolderOpen, setNewFolderOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const pageSize = 24;

  const foldersQuery = useQuery({
    queryKey: ["folders"],
    queryFn: () => api.get<Folder[]>("/folders"),
  });

  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (search) params.set("q", search);
  if (typeFilter) params.set("type", typeFilter);
  if (statusFilter) params.set("status", statusFilter);
  if (folderId) params.set("folder_id", folderId);

  const assetsQuery = useQuery({
    queryKey: ["assets", params.toString()],
    queryFn: () => api.get<Asset[]>(`/assets?${params.toString()}`),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["assets"] });
    queryClient.invalidateQueries({ queryKey: ["folders"] });
  };

  const createFolder = useMutation({
    mutationFn: (name: string) => api.post("/folders", { name, parent_id: folderId }),
    onSuccess: () => {
      setNewFolderOpen(false);
      setNewFolderName("");
      message.success("Folder created");
      invalidate();
    },
    onError: (err) =>
      message.error(err instanceof ApiError ? err.message : "Failed to create folder"),
  });

  const archiveFolder = useMutation({
    mutationFn: (id: string) => api.delete(`/folders/${id}`),
    onSuccess: () => {
      setFolderId(null);
      message.success("Folder archived");
      invalidate();
    },
    onError: (err) =>
      message.error(err instanceof ApiError ? err.message : "Failed to archive folder"),
  });

  const folders = foldersQuery.data?.data ?? [];
  const assets = assetsQuery.data?.data ?? [];
  const total = assetsQuery.data?.meta.total ?? 0;

  return (
    <PageContainer
        title="Content Library"
        description="Manage, organize and publish digital signage content."
        actions={
          canCreate && (
            <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadOpen(true)}>
              Upload content
            </Button>
          )
        }
      >

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={5}>
          <Card
            size="small"
            title="Folders"
            extra={
              canCreate && (
                <Button
                  type="text"
                  size="small"
                  icon={<FolderAddOutlined />}
                  aria-label="New folder"
                  onClick={() => setNewFolderOpen(true)}
                />
              )
            }
          >
            <Menu
              mode="inline"
              selectedKeys={[folderId ?? "__all__"]}
              style={{ borderInlineEnd: 0 }}
              onClick={({ key }) => {
                setFolderId(key === "__all__" ? null : key);
                setPage(1);
              }}
              items={[
                { key: "__all__", icon: <FolderOutlined />, label: "All content" },
                ...folders.map((folder) => ({
                  key: folder.id,
                  icon: <FolderOutlined />,
                  label: (
                    <span className="flex items-center">
                      <span className="truncate">{folder.name}</span>
                      {canDelete && (
                        <Popconfirm
                          title={`Archive folder "${folder.name}"?`}
                          onConfirm={(e) => {
                            e?.stopPropagation();
                            archiveFolder.mutate(folder.id);
                          }}
                          onCancel={(e) => e?.stopPropagation()}
                        >
                          <Button
                            type="text"
                            size="small"
                            danger
                            className="ml-auto"
                            aria-label={`Archive folder ${folder.name}`}
                            icon={<DeleteOutlined />}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </Popconfirm>
                      )}
                    </span>
                  ),
                })),
              ]}
            />
          </Card>
        </Col>

        <Col xs={24} lg={19}>
          <FilterBar
        search={<SearchBar value={search} onChange={(value) => { setSearch(value); setPage(1); }} placeholder="Search content…" label="Search content" width={256} />}
            onReset={
              search || typeFilter || statusFilter
                ? () => {
                    setSearch("");
                    setTypeFilter("");
                    setStatusFilter("");
                    setPage(1);
                  }
                : undefined
            }
          >
            <Select
              className="w-40"
              value={typeFilter}
              aria-label="Filter by type"
              onChange={(value) => {
                setTypeFilter(value);
                setPage(1);
              }}
              options={TYPE_FILTERS.map((t) => ({
                value: t,
                label: t ? t.charAt(0).toUpperCase() + t.slice(1) : "All types",
              }))}
            />
            <Select
              className="w-40"
              value={statusFilter}
              aria-label="Filter by status"
              onChange={(value) => {
                setStatusFilter(value);
                setPage(1);
              }}
              options={STATUS_FILTERS.map((s) => ({
                value: s,
                label: s ? s.charAt(0).toUpperCase() + s.slice(1) : "All statuses",
              }))}
            />
          </FilterBar>

          {assetsQuery.isLoading ? (
            <LoadingState rows={6} />
          ) : assets.length === 0 ? (
            <Card>
              <EmptyState
                title="No content here yet"
                description="Upload your first asset to get started."
                action={
                  canCreate && (
                    <Button
                      type="primary"
                      icon={<UploadOutlined />}
                      onClick={() => setUploadOpen(true)}
                    >
                      Upload content
                    </Button>
                  )
                }
              />
            </Card>
          ) : (
            <Row gutter={[12, 12]}>
              {assets.map((asset) => (
                <Col key={asset.id} xs={12} sm={8} xl={6}>
                  <Card
                    hoverable
                    size="small"
                    onClick={() => setDetailId(asset.id)}
                    tabIndex={0}
                    role="button"
                    aria-label={`Open ${asset.name}`}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") setDetailId(asset.id);
                    }}
                    cover={
                      <div className="flex h-28 items-center justify-center overflow-hidden dsc-fill">
                        {asset.thumbnail_url ? (
                          <img
                            src={asset.thumbnail_url}
                            alt={asset.name}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <span className="text-2xl uppercase dsc-text-secondary">
                            {asset.type.slice(0, 3)}
                          </span>
                        )}
                      </div>
                    }
                  >
                    <Typography.Text strong ellipsis className="block text-sm">
                      {asset.name}
                    </Typography.Text>
                    <div className="mt-1 flex items-center gap-2 text-xs dsc-text-secondary">
                      <StatusBadge status={asset.status} />
                      {asset.current_version && (
                        <span>{formatBytes(asset.current_version.size_bytes)}</span>
                      )}
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          )}

          {total > pageSize && (
            <div className="mt-4 flex justify-end">
              <Pagination
                current={page}
                pageSize={pageSize}
                total={total}
                showSizeChanger={false}
                showTotal={(t) => `${t} assets`}
                onChange={setPage}
              />
            </div>
          )}
        </Col>
      </Row>

      <Modal
        title="New folder"
        open={newFolderOpen}
        okText="Create"
        confirmLoading={createFolder.isPending}
        onOk={() => {
          if (newFolderName.trim()) createFolder.mutate(newFolderName.trim());
        }}
        onCancel={() => setNewFolderOpen(false)}
        destroyOnHidden
      >
        <Input
          autoFocus
          placeholder="Folder name"
          aria-label="Folder name"
          value={newFolderName}
          onChange={(e) => setNewFolderName(e.target.value)}
          onPressEnter={() => {
            if (newFolderName.trim()) createFolder.mutate(newFolderName.trim());
          }}
        />
      </Modal>

      {uploadOpen && (
        <UploadModal
          folderId={folderId}
          onClose={() => setUploadOpen(false)}
          onUploaded={invalidate}
        />
      )}
      {detailId && (
        <AssetDetailModal
          assetId={detailId}
          onClose={() => setDetailId(null)}
          onChanged={invalidate}
        />
      )}
    </PageContainer>
  );
}
