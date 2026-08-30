import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  Row,
  Space,
  Switch,
  Typography,
} from "antd";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface SsoProvider {
  id: string;
  issuer: string;
  client_id: string;
  client_secret_ref: string;
  claim_mapping: Record<string, unknown>;
  active: boolean;
  endpoints: Record<string, string> | null;
}

interface SsoFormValues {
  issuer: string;
  client_id: string;
  client_secret_ref: string;
  mapping: string;
  active: boolean;
}

/** P3-17 Enterprise SSO (OIDC): provider config with secrets by env-var
 * reference, claim mapping, discovery test and the tenant login URL. */
export function SsoSection() {
  const { hasPermission, user } = useAuth();
  const canManage = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [form] = Form.useForm<SsoFormValues>();

  const providerQuery = useQuery({
    queryKey: ["sso-provider"],
    queryFn: () => api.get<SsoProvider | null>("/sso/providers"),
    enabled: canManage,
    retry: false,
  });
  const provider = providerQuery.data?.data ?? null;

  useEffect(() => {
    if (provider) {
      form.setFieldsValue({
        issuer: provider.issuer,
        client_id: provider.client_id,
        client_secret_ref: provider.client_secret_ref,
        mapping: JSON.stringify(provider.claim_mapping, null, 2),
        active: provider.active,
      });
    }
  }, [provider, form]);

  const onError = (err: unknown) =>
    setMessage({
      kind: "error",
      text: err instanceof ApiError ? err.message : "Action failed",
    });
  const save = useMutation({
    mutationFn: (values: SsoFormValues) =>
      api.post("/sso/providers", {
        issuer: values.issuer,
        client_id: values.client_id,
        client_secret_ref: values.client_secret_ref,
        claim_mapping: values.mapping ? JSON.parse(values.mapping) : null,
        active: values.active,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sso-provider"] });
      setMessage({ kind: "ok", text: "SSO provider saved." });
    },
    onError,
  });
  const test = useMutation({
    mutationFn: () => api.post<{ ok: boolean; error?: string }>("/sso/providers/test", {}),
    onSuccess: (envelope) => {
      queryClient.invalidateQueries({ queryKey: ["sso-provider"] });
      const data = envelope.data!;
      setMessage(
        data.ok
          ? { kind: "ok", text: "Issuer discovery succeeded — endpoints cached." }
          : { kind: "error", text: `Discovery failed: ${data.error}` },
      );
    },
    onError,
  });

  if (!canManage) return null;
  if (providerQuery.isError) return null; // entitlement off → section absent

  function onFinish(values: SsoFormValues) {
    setMessage(null);
    try {
      if (values.mapping) JSON.parse(values.mapping);
    } catch {
      setMessage({ kind: "error", text: "Claim mapping must be valid JSON" });
      return;
    }
    save.mutate(values);
  }

  return (
    <Card size="small" title="Enterprise SSO (OIDC)">
      <Typography.Paragraph type="secondary" className="!mb-3">
        The IdP authenticates; roles stay platform-managed via claim
        mapping. The client secret is referenced by an environment-variable
        NAME — never stored here.
      </Typography.Paragraph>
      <Form
        form={form}
        layout="vertical"
        initialValues={{ active: false, mapping: "" }}
        onFinish={onFinish}
      >
        <Row gutter={12}>
          <Col xs={24} sm={8}>
            <Form.Item
              name="issuer"
              label="Issuer (https)"
              rules={[{ required: true, message: "Issuer is required" }]}
            >
              <Input placeholder="https://login.example.com" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item
              name="client_id"
              label="Client ID"
              rules={[{ required: true, message: "Client ID is required" }]}
            >
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item
              name="client_secret_ref"
              label="Client secret env-var NAME"
              rules={[{ required: true, message: "Secret env-var name is required" }]}
            >
              <Input placeholder="SSO_CLIENT_SECRET" />
            </Form.Item>
          </Col>
        </Row>
        <Form.Item
          name="mapping"
          label="Claim mapping (JSON — email/name/groups paths, role_map, auto_provision, default_role)"
        >
          <Input.TextArea
            rows={5}
            className="font-mono text-xs"
            placeholder='{"email": "email", "role_map": {"idp-group": "Organization Administrator"}, "auto_provision": false}'
          />
        </Form.Item>
        <Space wrap align="center">
          <Form.Item name="active" valuePropName="checked" noStyle>
            <Switch />
          </Form.Item>
          <Typography.Text>SSO enabled</Typography.Text>
          <Button type="primary" htmlType="submit" loading={save.isPending}>
            Save provider
          </Button>
          {provider && (
            <Button loading={test.isPending} onClick={() => test.mutate()}>
              Test connection
            </Button>
          )}
        </Space>
      </Form>
      {provider?.active && user && (
        <Alert
          type="info"
          className="mt-3"
          message={
            <>
              SSO entry point:{" "}
              <Typography.Text code>
                GET /api/v1/auth/sso/&lt;org-code&gt;/login?redirect_uri=&lt;portal-callback&gt;
              </Typography.Text>
            </>
          }
        />
      )}
      {message && (
        <Alert
          type={message.kind === "ok" ? "success" : "error"}
          message={message.text}
          showIcon
          className="mt-3"
          role={message.kind === "error" ? "alert" : undefined}
        />
      )}
    </Card>
  );
}
