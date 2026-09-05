import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Col, ColorPicker, Form, Input, Row, Typography } from "antd";
import { ToneTag } from "@/design-system";
import { SectionCard } from "@/design-system";
import { toneOf } from "@/design-system";
import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface WhiteLabel {
  custom_domain: string | null;
  domain_verified: boolean;
  email_from_name: string | null;
  email_from_address: string | null;
  region: string;
  branding: { logo_url?: string; primary_color?: string; app_name?: string };
}

interface WhiteLabelFormValues {
  custom_domain: string;
  email_from_name: string;
  email_from_address: string;
  logo_url: string;
  primary_color: string;
  app_name: string;
}

/** P3-16 White-Label Settings: theme, custom-domain metadata (verified by
 * the platform admin) and the tenant email sender identity. */
export function WhiteLabelSection() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("organization.manage");
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [form] = Form.useForm<WhiteLabelFormValues>();
  const customDomain = Form.useWatch("custom_domain", form);

  const query = useQuery({
    queryKey: ["white-label"],
    queryFn: () => api.get<WhiteLabel>("/organization/white-label"),
    retry: false,
  });
  const data = query.data?.data ?? null;

  useEffect(() => {
    if (data) {
      form.setFieldsValue({
        custom_domain: data.custom_domain ?? "",
        email_from_name: data.email_from_name ?? "",
        email_from_address: data.email_from_address ?? "",
        logo_url: data.branding.logo_url ?? "",
        primary_color: data.branding.primary_color ?? "#0f172a",
        app_name: data.branding.app_name ?? "",
      });
    }
  }, [data, form]);

  const onError = (err: unknown) =>
    setMessage({
      kind: "error",
      text: err instanceof ApiError ? err.message : "Save failed",
    });
  const save = useMutation({
    mutationFn: async (values: WhiteLabelFormValues) => {
      await api.put("/organization/white-label", {
        custom_domain: values.custom_domain || null,
        email_from_name: values.email_from_name || null,
        email_from_address: values.email_from_address || null,
      });
      await api.patch("/organization", {
        branding_json: {
          logo_url: values.logo_url || null,
          primary_color: values.primary_color,
          app_name: values.app_name || null,
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["white-label"] });
      setMessage({ kind: "ok", text: "White-label settings saved." });
    },
    onError,
  });

  if (!canManage || query.isError || !data) return null;

  return (
    <SectionCard title="White label">
      <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
        Theme + custom-domain metadata (DNS routing and verification are
        handled with the platform administrator) + the sender identity used
        for notification email. Region: {data.region}.
      </Typography.Paragraph>
      <Form
        form={form}
        layout="vertical"
        initialValues={{ primary_color: "#0f172a" }}
        onFinish={(values) => {
          setMessage(null);
          save.mutate(values);
        }}
      >
        <Row gutter={12}>
          <Col xs={24} sm={8}>
            <Form.Item
              name="custom_domain"
              label={
                <>
                  Custom domain{" "}
                  {customDomain && (
                    <ToneTag tone={toneOf(data.domain_verified ? "success" : "warning")}
                      className="ms-1"
                    >
                      {data.domain_verified ? "verified" : "pending verification"}
                    </ToneTag>
                  )}
                </>
              }
            >
              <Input placeholder="signage.yourcompany.com" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item name="email_from_name" label="Email sender name">
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item
              name="email_from_address"
              label="Email sender address"
              rules={[{ type: "email", message: "Must be a valid email address" }]}
            >
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item name="app_name" label="Portal name">
              <Input placeholder="Acme Signage" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item name="logo_url" label="Logo URL">
              <Input />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item
              name="primary_color"
              label="Primary color"
              getValueFromEvent={(color) => color.toHexString()}
            >
              <ColorPicker showText format="hex" />
            </Form.Item>
          </Col>
        </Row>
        <Button type="primary" htmlType="submit" loading={save.isPending}>
          Save white label
        </Button>
      </Form>
      {message && (
        <Alert
          type={message.kind === "ok" ? "success" : "error"}
          message={message.text}
          showIcon
          className="mt-3"
          role={message.kind === "error" ? "alert" : undefined}
        />
      )}
    </SectionCard>
  );
}
