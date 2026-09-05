import {
  DeleteOutlined,
  DragOutlined,
  EditOutlined,
  EnvironmentOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  App,
  Button,
  Card,
  Col,
  Descriptions,
  Flex,
  Popconfirm,
  Row,
  Space,
  Tree,
  Typography,
  type TreeDataNode,
} from "antd";
import { ToneTag } from "@/design-system";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageContainer } from "@/design-system";
import { EmptyState, ErrorState, LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { LocationFormModal } from "./LocationFormModal";
import { MoveLocationModal } from "./MoveLocationModal";
import { TagEditor } from "./TagEditor";
import type { LocationDetail, TreeEntry } from "./types";

function toTreeData(entries: TreeEntry[]): TreeDataNode[] {
  return entries.map(({ node, children }) => ({
    key: node.id,
    title: (
      <span>
        {node.name}
        {node.type && (
          <Typography.Text type="secondary" className="ml-2 text-xs">
            {node.type.name}
          </Typography.Text>
        )}
      </span>
    ),
    children: children.length > 0 ? toTreeData(children) : undefined,
  }));
}

/** SCR-06 Location Tree + SCR-07 Location Details (master-detail). */
export function LocationsPage() {
  const { hasPermission } = useAuth();
  const { message } = App.useApp();
  const canManage = hasPermission("locations.manage");
  const queryClient = useQueryClient();

  const [searchParams] = useSearchParams();
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("id"));
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
      message.success("Location archived");
    },
    onError: (err) =>
      message.error(err instanceof ApiError ? err.message : "Failed to archive location"),
  });

  const tree = treeQuery.data?.data ?? [];
  const treeData = useMemo(() => toTreeData(tree), [tree]);
  const detail = detailQuery.data?.data ?? null;

  return (
    <PageContainer
        title="Locations"
        description="Organize your estate in a hierarchy — regions, cities, sites, zones."
        actions={
          canManage && (
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setModal({ kind: "create", parentId: null, parentName: null })}
            >
              Add root location
            </Button>
          )
        }
      >

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={9}>
          <Card size="small" title="Hierarchy">
            {treeQuery.isLoading ? (
              <LoadingState rows={5} />
            ) : treeQuery.isError ? (
              <ErrorState
                title="Unable to load the location tree"
                onRetry={() => treeQuery.refetch()}
              />
            ) : tree.length === 0 ? (
              <EmptyState
                title="No locations yet"
                description="Create the first root node to start the hierarchy."
                action={
                  canManage && (
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() =>
                        setModal({ kind: "create", parentId: null, parentName: null })
                      }
                    >
                      Add root location
                    </Button>
                  )
                }
              />
            ) : (
              <Tree
                treeData={treeData}
                defaultExpandAll
                selectedKeys={selectedId ? [selectedId] : []}
                onSelect={(keys) => setSelectedId((keys[0] as string) ?? null)}
                showLine={{ showLeafIcon: false }}
                aria-label="Location hierarchy"
              />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={15}>
          <Card size="small" title="Details">
            {!selectedId ? (
              <EmptyState
                title="Select a location"
                description="Pick a node in the hierarchy to see its details."
              />
            ) : detailQuery.isLoading ? (
              <LoadingState rows={5} />
            ) : !detail ? (
              <ErrorState
                title="Unable to load location details"
                onRetry={() => detailQuery.refetch()}
              />
            ) : (
              <div>
                <Flex wrap justify="space-between" align="flex-start" gap="small">
                  <Space orientation="vertical" size={0}>
                    <Space align="center">
                      <EnvironmentOutlined className="text-slate-600 dark:text-slate-400" />
                      <Typography.Title level={5} className="!mb-0">
                        {detail.name}
                      </Typography.Title>
                      {detail.code && <ToneTag tone="default">{detail.code}</ToneTag>}
                    </Space>
                    <Space size="small">
                      <Typography.Text type="secondary">
                        {detail.type?.name ?? "Untyped"} · depth {detail.depth}
                      </Typography.Text>
                      <StatusBadge status={detail.status} />
                    </Space>
                  </Space>
                  {canManage && (
                    <Space wrap>
                      <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        onClick={() =>
                          setModal({
                            kind: "create",
                            parentId: detail.id,
                            parentName: detail.name,
                          })
                        }
                      >
                        Add child
                      </Button>
                      <Button
                        icon={<EditOutlined />}
                        onClick={() => setModal({ kind: "edit", detail })}
                      >
                        Edit
                      </Button>
                      <Button
                        icon={<DragOutlined />}
                        onClick={() => setModal({ kind: "move", detail })}
                      >
                        Move
                      </Button>
                      <Popconfirm
                        title={`Archive "${detail.name}"?`}
                        onConfirm={() => archive.mutate(detail.id)}
                        okButtonProps={{ danger: true }}
                      >
                        <Button danger icon={<DeleteOutlined />}>
                          Archive
                        </Button>
                      </Popconfirm>
                    </Space>
                  )}
                </Flex>

                <Descriptions
                  className="mt-5"
                  column={{ xs: 1, sm: 2 }}
                  size="small"
                  items={[
                    { label: "Effective timezone", children: detail.effective_timezone },
                    { label: "Own timezone", children: detail.timezone ?? "inherited" },
                    { label: "Address", children: detail.address ?? "—" },
                    {
                      label: "Coordinates",
                      children:
                        detail.latitude != null && detail.longitude != null
                          ? `${detail.latitude}, ${detail.longitude}`
                          : "—",
                    },
                    { label: "Direct children", children: String(detail.children_count) },
                    { label: "Total descendants", children: String(detail.descendants_count) },
                  ]}
                />

                <div className="mt-6">
                  <TagEditor detail={detail} canManage={canManage} onSaved={invalidate} />
                </div>
              </div>
            )}
          </Card>
        </Col>
      </Row>

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
    </PageContainer>
  );
}
