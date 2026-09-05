import { PlusOutlined, SearchOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Flex,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
  type TableProps,
} from "antd";
import { useState } from "react";
import { ErrorState, EmptyState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Role, UserRow } from "./types";

export function UsersTab() {
  const { hasPermission, user: sessionUser } = useAuth();
  const canManage = hasPermission("users.manage");
  const queryClient = useQueryClient();

  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRow | null>(null);
  const pageSize = 20;

  const usersQuery = useQuery({
    queryKey: ["users", { search, page }],
    queryFn: () =>
      api.get<UserRow[]>(
        `/users?page=${page}&page_size=${pageSize}${search ? `&q=${encodeURIComponent(search)}` : ""}`,
      ),
  });

  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles"),
    enabled: canManage,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  const deactivate = useMutation({
    mutationFn: (id: string) => api.delete(`/users/${id}`),
    onSuccess: invalidate,
  });
  const activate = useMutation({
    mutationFn: (id: string) => api.post(`/users/${id}/activate`),
    onSuccess: invalidate,
  });

  const users = usersQuery.data?.data ?? [];
  const total = usersQuery.data?.meta.total ?? 0;

  const columns: TableProps<UserRow>["columns"] = [
    {
      title: "Name",
      dataIndex: "full_name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    { title: "Email", dataIndex: "email" },
    {
      title: "Roles",
      responsive: ["lg"],
      render: (_, user) => user.roles.map((r) => r.name).join(", ") || "—",
    },
    {
      title: "Status",
      dataIndex: "status",
      render: (status: string) => <StatusBadge status={status} />,
    },
    ...(canManage
      ? [
          {
            title: "Actions",
            align: "right" as const,
            render: (_: unknown, user: UserRow) => (
              <Space>
                <Button type="link" size="small" onClick={() => setEditingUser(user)}>
                  Edit
                </Button>
                {user.id !== sessionUser?.id &&
                  (user.status === "deactivated" ? (
                    <Button
                      type="link"
                      size="small"
                      onClick={() => activate.mutate(user.id)}
                    >
                      Activate
                    </Button>
                  ) : (
                    <Popconfirm
                      title={`Deactivate ${user.email}?`}
                      okButtonProps={{ danger: true }}
                      onConfirm={() => deactivate.mutate(user.id)}
                    >
                      <Button type="link" size="small" danger>
                        Deactivate
                      </Button>
                    </Popconfirm>
                  ))}
              </Space>
            ),
          },
        ]
      : []),
  ];

  return (
    <div>
      <Flex wrap gap="small" align="center" justify="space-between" className="mb-4">
        <Input
          allowClear
          className="w-72"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search by name or email…"
          aria-label="Search users"
          prefix={<SearchOutlined className="text-slate-600 dark:text-slate-400" />}
        />
        {canManage && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            Add user
          </Button>
        )}
      </Flex>

      {usersQuery.isError ? (
        <ErrorState title="Failed to load users" onRetry={() => usersQuery.refetch()} />
      ) : (
        <Table<UserRow>
          size="middle"
          rowKey="id"
          columns={columns}
          dataSource={users}
          loading={usersQuery.isLoading}
          scroll={{ x: "max-content" }}
          locale={{ emptyText: <EmptyState title="No users match your search" /> }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: false,
            showTotal: (t) => `${t} users`,
            onChange: setPage,
          }}
        />
      )}

      <CreateUserModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        roles={rolesQuery.data?.data ?? []}
        onCreated={invalidate}
      />
      {editingUser && (
        <EditUserModal
          user={editingUser}
          roles={rolesQuery.data?.data ?? []}
          onClose={() => setEditingUser(null)}
          onSaved={() => {
            invalidate();
            setEditingUser(null);
          }}
        />
      )}
    </div>
  );
}

function EditUserModal({
  user,
  roles,
  onClose,
  onSaved,
}: {
  user: UserRow;
  roles: Role[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form] = Form.useForm<{ full_name: string; role_ids: string[] }>();
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (values: { full_name: string; role_ids: string[] }) =>
      api.patch(`/users/${user.id}`, {
        full_name: values.full_name,
        role_ids: values.role_ids,
      }),
    onSuccess: onSaved,
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to update user"),
  });

  return (
    <Modal
      title={`Edit user: ${user.email}`}
      open
      onCancel={onClose}
      okText="Save"
      confirmLoading={save.isPending}
      onOk={() => form.submit()}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          full_name: user.full_name,
          role_ids: user.roles.map((r) => r.id),
        }}
        onFinish={(values) => {
          setError(null);
          save.mutate(values);
        }}
      >
        <Form.Item
          name="full_name"
          label="Full name"
          rules={[{ required: true, message: "Full name is required" }]}
        >
          <Input />
        </Form.Item>
        <Form.Item name="role_ids" label="Roles">
          <Select
            mode="multiple"
            placeholder="Select roles…"
            aria-label="Roles"
            options={roles.map((role) => ({ value: role.id, label: role.name }))}
          />
        </Form.Item>
        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Form>
    </Modal>
  );
}

function CreateUserModal({
  open,
  onClose,
  roles,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  roles: Role[];
  onCreated: () => void;
}) {
  const [form] = Form.useForm<{
    email: string;
    full_name: string;
    password?: string;
    role_ids: string[];
  }>();
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (values: {
      email: string;
      full_name: string;
      password?: string;
      role_ids: string[];
    }) =>
      api.post("/users", {
        email: values.email,
        full_name: values.full_name,
        password: values.password || null,
        role_ids: values.role_ids,
      }),
    onSuccess: () => {
      onCreated();
      onClose();
      form.resetFields();
      setError(null);
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to create user"),
  });

  return (
    <Modal
      title="Add user"
      open={open}
      onCancel={onClose}
      okText="Create user"
      confirmLoading={create.isPending}
      onOk={() => form.submit()}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ role_ids: [] }}
        onFinish={(values) => {
          setError(null);
          create.mutate(values);
        }}
      >
        <Form.Item
          name="email"
          label="Email"
          rules={[
            { required: true, message: "Email is required" },
            { type: "email", message: "Enter a valid email" },
          ]}
        >
          <Input type="email" />
        </Form.Item>
        <Form.Item
          name="full_name"
          label="Full name"
          rules={[{ required: true, message: "Full name is required" }]}
        >
          <Input />
        </Form.Item>
        <Form.Item
          name="password"
          label="Password (leave empty to invite)"
          rules={[{ min: 8, message: "At least 8 characters" }]}
        >
          <Input.Password autoComplete="new-password" />
        </Form.Item>
        <Form.Item name="role_ids" label="Roles">
          <Select
            mode="multiple"
            placeholder="Select roles…"
            aria-label="Roles"
            options={roles.map((role) => ({ value: role.id, label: role.name }))}
          />
        </Form.Item>
        {error && <Alert type="error" message={error} showIcon role="alert" />}
      </Form>
    </Modal>
  );
}
