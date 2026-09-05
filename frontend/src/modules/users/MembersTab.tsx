import { UserAddOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
  type TableProps,
} from "antd";
import { ToneTag } from "@/design-system";
import { toneOf } from "@/design-system";
import { useState } from "react";
import { EmptyState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface MemberRow {
  user_id: string;
  membership_id?: string;
  email: string;
  full_name: string;
  status: string;
  kind: "home" | "guest";
  is_owner: boolean;
  roles: string[];
}

interface RoleRow {
  id: string;
  name: string;
}

/** Tenant members (SaaS core): home users plus guest memberships — users
 * whose home is another organization but who were granted a role here. */
export function MembersTab() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("members.manage");
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [form] = Form.useForm<{ email: string; role_id: string }>();

  const membersQuery = useQuery({
    queryKey: ["org-members"],
    queryFn: () => api.get<MemberRow[]>("/organization/members"),
  });
  const rolesQuery = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<RoleRow[]>("/roles"),
  });

  const done = (text: string) => {
    queryClient.invalidateQueries({ queryKey: ["org-members"] });
    setMessage({ kind: "ok", text });
  };
  const onError = (err: unknown) =>
    setMessage({
      kind: "error",
      text: err instanceof ApiError ? err.message : "Action failed",
    });

  const addMember = useMutation({
    mutationFn: (values: { email: string; role_id: string }) =>
      api.post("/organization/members", {
        email: values.email,
        role_id: values.role_id,
        is_owner: false,
      }),
    onSuccess: () => {
      done("Member added.");
      form.resetFields(["email"]);
    },
    onError,
  });
  const removeMember = useMutation({
    mutationFn: (membershipId: string) =>
      api.delete(`/organization/members/${membershipId}`),
    onSuccess: () => done("Member removed."),
    onError,
  });

  const members = membersQuery.data?.data ?? [];
  const roles = rolesQuery.data?.data ?? [];

  const columns: TableProps<MemberRow>["columns"] = [
    { title: "Email", dataIndex: "email" },
    {
      title: "Name",
      dataIndex: "full_name",
      render: (name: string) => <Typography.Text strong>{name}</Typography.Text>,
    },
    {
      title: "Type",
      dataIndex: "kind",
      render: (kind: MemberRow["kind"]) => (
        <ToneTag tone={toneOf(kind === "guest" ? "blue" : "default")}>
          {kind}
        </ToneTag>
      ),
    },
    {
      title: "Roles",
      responsive: ["lg"],
      render: (_, member) => member.roles.join(", ") || "—",
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
            render: (_: unknown, member: MemberRow) =>
              member.kind === "guest" && member.membership_id ? (
                <Popconfirm
                  title={`Remove ${member.email} from this organization?`}
                  okButtonProps={{ danger: true }}
                  onConfirm={() => removeMember.mutate(member.membership_id!)}
                >
                  <Button size="small" danger>
                    Remove
                  </Button>
                </Popconfirm>
              ) : null,
          },
        ]
      : []),
  ];

  return (
    <Space orientation="vertical" size="medium" className="w-full">
      <Typography.Text type="secondary">
        Home users belong to this organization; guests are users from another
        organization granted a role here.
      </Typography.Text>

      <Table<MemberRow>
        size="medium"
        rowKey="user_id"
        columns={columns}
        dataSource={members}
        loading={membersQuery.isLoading}
        pagination={false}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: <EmptyState title="No members yet" /> }}
      />

      {canManage && (
        <Card size="small">
          <Form
            form={form}
            layout="inline"
            onFinish={(values) => {
              setMessage(null);
              addMember.mutate(values);
            }}
          >
            <Form.Item
              name="email"
              label="Existing user's email"
              rules={[
                { required: true, message: "Email is required" },
                { type: "email", message: "Enter a valid email" },
              ]}
            >
              <Input type="email" className="w-64" />
            </Form.Item>
            <Form.Item
              name="role_id"
              label="Role"
              rules={[{ required: true, message: "Role is required" }]}
            >
              <Select
                className="w-44"
                placeholder="Select role…"
                aria-label="Role"
                options={roles.map((r) => ({ value: r.id, label: r.name }))}
                loading={rolesQuery.isLoading}
              />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                icon={<UserAddOutlined />}
                loading={addMember.isPending}
              >
                Add member
              </Button>
            </Form.Item>
          </Form>
        </Card>
      )}

      {message && (
        <Alert
          type={message.kind === "ok" ? "success" : "error"}
          message={message.text}
          showIcon
          role={message.kind === "error" ? "alert" : undefined}
        />
      )}
    </Space>
  );
}
