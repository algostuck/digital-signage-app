import { PlusOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Drawer,
  Flex,
  Form,
  Input,
  Row,
  Space,
  Tooltip,
  Typography,
} from "antd";
import { ToneTag } from "@/design-system";
import { useMemo, useState } from "react";
import { ErrorState, LoadingState } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Permission, Role } from "./types";

export function RolesTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("roles.manage");
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Role | "new" | null>(null);

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles"),
  });
  const permissionsQuery = useQuery({
    queryKey: ["permissions"],
    queryFn: () => api.get<Permission[]>("/permissions"),
  });

  const roles = rolesQuery.data?.data ?? [];
  const permissions = permissionsQuery.data?.data ?? [];

  if (rolesQuery.isLoading) return <LoadingState rows={6} />;
  if (rolesQuery.isError)
    return <ErrorState title="Failed to load roles" onRetry={() => rolesQuery.refetch()} />;

  return (
    <div>
      {canManage && (
        <Flex justify="flex-end" className="mb-4">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setEditing("new")}>
            Add role
          </Button>
        </Flex>
      )}
      <Row gutter={[16, 16]}>
        {roles.map((role) => (
          <Col key={role.id} xs={24} lg={12}>
            <Card
              size="small"
              title={
                <Space>
                  {role.name}
                  {role.is_system && <ToneTag tone="default">System</ToneTag>}
                </Space>
              }
              extra={
                canManage &&
                !role.is_system && (
                  <Button type="link" size="small" onClick={() => setEditing(role)}>
                    Edit
                  </Button>
                )
              }
            >
              {role.description && (
                <Typography.Paragraph type="secondary" className="!mb-2">
                  {role.description}
                </Typography.Paragraph>
              )}
              <Typography.Text type="secondary" className="text-xs uppercase tracking-wide">
                {role.permissions.length} permissions
              </Typography.Text>
              <Flex wrap gap={4} className="mt-1">
                {role.permissions.slice(0, 12).map((p) => (
                  <ToneTag tone="default" key={p.code} className="!me-0 text-xs">
                    {p.code}
                  </ToneTag>
                ))}
                {role.permissions.length > 12 && (
                  <Typography.Text type="secondary" className="text-xs">
                    +{role.permissions.length - 12} more
                  </Typography.Text>
                )}
              </Flex>
            </Card>
          </Col>
        ))}
      </Row>

      {editing && (
        <RoleDrawer
          role={editing === "new" ? null : editing}
          permissions={permissions}
          onClose={() => setEditing(null)}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ["roles"] });
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}

function RoleDrawer({
  role,
  permissions,
  onClose,
  onSaved,
}: {
  role: Role | null;
  permissions: Permission[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form] = Form.useForm<{ name: string; description?: string }>();
  const [codes, setCodes] = useState<Set<string>>(
    new Set(role?.permissions.map((p) => p.code) ?? []),
  );
  const [error, setError] = useState<string | null>(null);

  const grouped = useMemo(() => {
    const groups = new Map<string, Permission[]>();
    for (const p of permissions) {
      const domain = p.code.split(".")[0];
      groups.set(domain, [...(groups.get(domain) ?? []), p]);
    }
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [permissions]);

  const save = useMutation({
    mutationFn: (values: { name: string; description?: string }) => {
      const body = {
        name: values.name,
        description: values.description || null,
        permission_codes: [...codes],
      };
      return role ? api.patch(`/roles/${role.id}`, body) : api.post("/roles", body);
    },
    onSuccess: onSaved,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to save role"),
  });

  function toggle(code: string, checked: boolean) {
    setCodes((prev) => {
      const next = new Set(prev);
      if (checked) next.add(code);
      else next.delete(code);
      return next;
    });
  }

  return (
    <Drawer
      title={role ? `Edit role: ${role.name}` : "Add role"}
      open
      size={600}
      onClose={onClose}
      footer={
        <Flex justify="flex-end" gap="small">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="primary" loading={save.isPending} onClick={() => form.submit()}>
            Save role
          </Button>
        </Flex>
      }
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ name: role?.name ?? "", description: role?.description ?? "" }}
        onFinish={(values) => {
          setError(null);
          save.mutate(values);
        }}
      >
        <Form.Item
          name="name"
          label="Name"
          rules={[{ required: true, message: "Name is required" }]}
        >
          <Input />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input />
        </Form.Item>
        <Form.Item label="Permissions">
          <Space orientation="vertical" size="middle" className="w-full">
            {grouped.map(([domain, perms]) => (
              <div key={domain}>
                <Typography.Text
                  type="secondary"
                  strong
                  className="text-xs uppercase tracking-wide"
                >
                  {domain}
                </Typography.Text>
                <Flex vertical gap={4} className="mt-1">
                  {perms.map((p) => (
                    <Tooltip key={p.code} title={p.description ?? undefined} placement="left">
                      <Checkbox
                        checked={codes.has(p.code)}
                        onChange={(e) => toggle(p.code, e.target.checked)}
                      >
                        {p.code}
                      </Checkbox>
                    </Tooltip>
                  ))}
                </Flex>
              </div>
            ))}
          </Space>
        </Form.Item>
        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Form>
    </Drawer>
  );
}
