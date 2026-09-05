import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Checkbox, Col, Divider, Form, Input, InputNumber, Row, Space, Switch, Typography } from "antd";
import { EntityDrawer } from "@/design-system";
import { useEffect } from "react";
import { api } from "../../lib/api";
import { useEntitlementCatalogue, usePlatformFeedback } from "./api";
import { entitlementLabel, type PlanRow } from "./types";

interface Values {
  code: string;
  name: string;
  description?: string;
  currency: string;
  monthly?: number | null;
  yearly?: number | null;
  sort_order: number;
  is_active: boolean;
  limits: Record<string, number | null>;
  features: Record<string, boolean>;
}

/** Create or edit a plan. The limit and feature fields are generated from
 * the backend's entitlement catalogue, so the form can never drift from
 * what the entitlement engine understands. */
export function PlanDrawer({
  open,
  plan,
  onClose,
}: {
  open: boolean;
  /** Null creates a new plan. */
  plan: PlanRow | null;
  onClose(): void;
}) {
  const [form] = Form.useForm<Values>();
  const feedback = usePlatformFeedback();
  const catalogue = useEntitlementCatalogue();
  const keys = catalogue.data?.data ?? {};
  const intKeys = Object.keys(keys).filter((k) => keys[k] === "int");
  const boolKeys = Object.keys(keys).filter((k) => keys[k] === "bool");
  const editing = plan != null;

  useEffect(() => {
    if (!open) return;
    if (!plan) {
      form.resetFields();
      return;
    }
    form.setFieldsValue({
      code: plan.code,
      name: plan.name,
      description: plan.description ?? "",
      currency: plan.prices.monthly?.currency ?? plan.prices.yearly?.currency ?? "INR",
      monthly: plan.prices.monthly?.amount ?? null,
      yearly: plan.prices.yearly?.amount ?? null,
      sort_order: plan.sort_order,
      is_active: plan.is_active,
      limits: Object.fromEntries(
        plan.entitlements.filter((e) => e.int_value !== null).map((e) => [e.key, e.int_value]),
      ),
      features: Object.fromEntries(
        plan.entitlements.filter((e) => e.bool_value !== null).map((e) => [e.key, e.bool_value === true]),
      ),
    });
  }, [open, plan, form]);

  const save = useMutation({
    mutationFn: (values: Values) => {
      const prices: PlanRow["prices"] = {};
      if (values.monthly != null) prices.monthly = { amount: Number(values.monthly), currency: values.currency };
      if (values.yearly != null) prices.yearly = { amount: Number(values.yearly), currency: values.currency };
      return api.post("/platform/plans", {
        code: values.code.trim(),
        name: values.name.trim(),
        description: values.description?.trim() || null,
        prices,
        entitlements: [
          ...intKeys
            .filter((k) => values.limits?.[k] != null)
            .map((k) => ({ key: k, int_value: Number(values.limits[k]) })),
          ...boolKeys.map((k) => ({ key: k, bool_value: values.features?.[k] ?? false })),
        ],
        is_active: values.is_active,
        sort_order: Number(values.sort_order) || 0,
      });
    },
    onSuccess: (_d, values) => {
      feedback.done(editing ? `Plan "${values.name}" updated.` : `Plan "${values.name}" created.`);
      onClose();
    },
    onError: feedback.onError,
  });

  return (
    <EntityDrawer
      title={editing ? `Edit plan — ${plan.name}` : "New plan"}
      open={open}
      onClose={onClose}
      size="wide"
      destroyOnHidden
      footer={
        <Space className="w-full justify-end">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="primary" loading={save.isPending} onClick={() => form.submit()}>
            {editing ? "Save changes" : "Create plan"}
          </Button>
        </Space>
      }
    >
      {editing && (
        <Alert
          type="info"
          showIcon
          className="mb-4"
          message="Changes apply to every tenant on this plan at their next entitlement check. Existing quota overrides still cap below the plan."
        />
      )}
      <Form
        form={form}
        layout="vertical"
        requiredMark="optional"
        initialValues={{ currency: "INR", sort_order: 0, is_active: true, limits: {}, features: {} }}
        onFinish={(values) => save.mutate(values)}
      >
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item
              name="code"
              label="Code"
              extra={editing ? "Codes are permanent." : "Lowercase, no spaces. Permanent once created."}
              rules={[
                { required: true, message: "Enter a code." },
                { pattern: /^[a-z0-9][a-z0-9_-]*$/, message: "Lowercase letters, digits, hyphens or underscores." },
              ]}
            >
              <Input disabled={editing} maxLength={50} autoFocus={!editing} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="name" label="Name" rules={[{ required: true, message: "Enter a name." }]}>
              <Input maxLength={100} autoFocus={editing} />
            </Form.Item>
          </Col>
          <Col xs={24}>
            <Form.Item name="description" label="Description">
              <Input.TextArea rows={2} maxLength={500} showCount />
            </Form.Item>
          </Col>
        </Row>

        <Divider titlePlacement="start" plain>
          Pricing
        </Divider>
        <Row gutter={16}>
          <Col xs={8}>
            <Form.Item
              name="currency"
              label="Currency"
              normalize={(v: string) => v.toUpperCase()}
              rules={[{ len: 3, message: "ISO code, e.g. INR." }]}
            >
              <Input maxLength={3} />
            </Form.Item>
          </Col>
          <Col xs={8}>
            <Form.Item name="monthly" label="Monthly" extra="Blank = custom quote">
              <InputNumber min={0} className="w-full" />
            </Form.Item>
          </Col>
          <Col xs={8}>
            <Form.Item name="yearly" label="Yearly">
              <InputNumber min={0} className="w-full" />
            </Form.Item>
          </Col>
        </Row>

        <Divider titlePlacement="start" plain>
          Limits
        </Divider>
        <Typography.Paragraph type="secondary" className="text-xs" style={{ marginBottom: 12 }}>
          Blank means unlimited.
        </Typography.Paragraph>
        <Row gutter={16}>
          {intKeys.map((key) => (
            <Col key={key} xs={12} sm={8}>
              <Form.Item name={["limits", key]} label={entitlementLabel(key)}>
                <InputNumber min={0} className="w-full" placeholder="Unlimited" />
              </Form.Item>
            </Col>
          ))}
        </Row>

        <Divider titlePlacement="start" plain>
          Features
        </Divider>
        <Row gutter={[16, 8]}>
          {boolKeys.map((key) => (
            <Col key={key} xs={12} sm={8}>
              <Form.Item name={["features", key]} valuePropName="checked" style={{ marginBottom: 4 }}>
                <Checkbox>{entitlementLabel(key)}</Checkbox>
              </Form.Item>
            </Col>
          ))}
        </Row>

        <Divider titlePlacement="start" plain>
          Availability
        </Divider>
        <Row gutter={16} align="middle">
          <Col xs={12}>
            <Form.Item name="is_active" label="Open for subscription" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Col>
          <Col xs={12}>
            <Form.Item name="sort_order" label="Display order" extra="Lower shows first">
              <InputNumber className="w-full" />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </EntityDrawer>
  );
}
