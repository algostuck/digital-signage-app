import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Col, Form, Input, Row, Select, Space, Tabs } from "antd";
import { useEffect, useState } from "react";
import { PageHeader } from "@/design-system";
import { ErrorState, LoadingState, LOCALE_OPTIONS, SectionCard, timeZoneOptions } from "@/design-system";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { ApprovalPolicySection } from "./ApprovalPolicySection";
import { DataSourcesSection } from "./DataSourcesSection";
import { EventBusSection } from "./EventBusSection";
import { IntegrationCatalogSection } from "./IntegrationCatalogSection";
import { IntegrationsSection } from "./IntegrationsSection";
import { PlanBillingSection } from "./PlanBillingSection";
import { SsoSection } from "./SsoSection";
import { WhiteLabelSection } from "./WhiteLabelSection";
import { QuotasRetentionSection } from "./QuotasRetentionSection";

interface Organization {
  id: string;
  name: string;
  code: string;
  status: string;
  timezone: string;
  locale: string;
  branding_json: Record<string, unknown> | null;
  quotas_json: Record<string, unknown> | null;
}

interface ProfileFormValues {
  name: string;
  timezone: string;
  locale: string;
}

/** SCR-03 Organizations / Tenant Settings. */
export function OrganizationSettingsPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission("organization.manage");
  const canSettings = hasPermission("settings.manage");
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("general");

  const orgQuery = useQuery({
    queryKey: ["organization"],
    queryFn: () => api.get<Organization>("/organization"),
  });

  const [form] = Form.useForm<ProfileFormValues>();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const org = orgQuery.data?.data ?? null;
  useEffect(() => {
    if (org) {
      form.setFieldsValue({
        name: org.name,
        timezone: org.timezone,
        locale: org.locale,
      });
    }
  }, [org, form]);

  const save = useMutation({
    mutationFn: (values: ProfileFormValues) =>
      api.patch("/organization", {
        name: values.name,
        timezone: values.timezone,
        locale: values.locale,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization"] });
      setMessage({ kind: "ok", text: "Organization settings saved." });
    },
    onError: (err) =>
      setMessage({
        kind: "error",
        text: err instanceof ApiError ? err.message : "Failed to save settings",
      }),
  });

  if (orgQuery.isLoading) return <LoadingState rows={8} />;
  if (orgQuery.isError || !org)
    return <ErrorState title="Failed to load organization." />;

  const generalTab = (
    <Space orientation="vertical" size="medium" className="w-full">
      <SectionCard title="Organization profile" description="Name, time zone and default locale for everyone in this tenant.">
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => {
            setMessage(null);
            save.mutate(values);
          }}
        >
          <Row gutter={12}>
            <Col xs={24} sm={8}>
              <Form.Item
                name="name"
                label="Organization name"
                rules={[{ required: true, message: "Enter the organization name." }]}
              >
                <Input disabled={!canManage} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item
                name="timezone"
                label="Time zone"
                rules={[{ required: true, message: "Choose a time zone." }]}
              >
                <Select showSearch disabled={!canManage} options={timeZoneOptions()} optionFilterProp="label" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8}>
              <Form.Item
                name="locale"
                label="Default locale"
                rules={[{ required: true, message: "Choose a default locale." }]}
              >
                <Select disabled={!canManage} options={LOCALE_OPTIONS} />
              </Form.Item>
            </Col>
          </Row>
          {message && (
            <Alert
              type={message.kind === "ok" ? "success" : "error"}
              message={message.text}
              showIcon
              className="mb-3"
              role="alert"
            />
          )}
          {canManage && (
            <Button type="primary" htmlType="submit" loading={save.isPending}>
              Save settings
            </Button>
          )}
        </Form>
      </SectionCard>
      <ApprovalPolicySection canManage={canManage} />
    </Space>
  );

  const planTab = (
    <Space orientation="vertical" size="medium" className="w-full">
      <PlanBillingSection />
      <QuotasRetentionSection />
    </Space>
  );

  const integrationsTab = (
    <Space orientation="vertical" size="medium" className="w-full">
      <IntegrationCatalogSection />
      <IntegrationsSection />
      <EventBusSection />
      <DataSourcesSection />
    </Space>
  );

  const brandingTab = (
    <Space orientation="vertical" size="medium" className="w-full">
      <WhiteLabelSection />
      <SsoSection />
    </Space>
  );

  return (
    <div>
      <PageHeader
        title="Organization Settings"
        description={`Tenant ${org.code} · status ${org.status}`}
      />
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: "general", label: "General", children: generalTab },
          { key: "plan", label: "Plan & usage", children: planTab },
          { key: "integrations", label: "Integrations", children: integrationsTab },
          ...(canManage || canSettings
            ? [{ key: "branding", label: "Branding & SSO", children: brandingTab }]
            : []),
        ]}
      />
    </div>
  );
}
