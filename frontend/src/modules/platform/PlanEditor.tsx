import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Typography,
} from "antd";
import { useState } from "react";
import { api, ApiError } from "../../lib/api";

interface EntitlementRow {
  key: string;
  int_value: number | null;
  bool_value: boolean | null;
}

export interface PlanRow {
  code: string;
  name: string;
  description: string | null;
  prices: Record<string, { amount: number; currency: string }>;
  is_active: boolean;
  sort_order: number;
  entitlements: EntitlementRow[];
}

interface PlanFormValues {
  code: string;
  name: string;
  description?: string;
  monthly?: number | null;
  yearly?: number | null;
  currency: string;
  is_active: boolean;
  sort_order?: number | null;
}

const EMPTY_FORM: PlanFormValues = {
  code: "",
  name: "",
  description: "",
  monthly: null,
  yearly: null,
  currency: "INR",
  is_active: true,
  sort_order: 0,
};

/** Super Admin plan editor: create a plan or edit an existing one. The
 * entitlement catalogue (key -> int|bool) comes from the backend so the
 * form always matches the engine. */
export function PlanEditor({ plans }: { plans: PlanRow[] }) {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<PlanFormValues>();
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [editing, setEditing] = useState<string>(""); // plan code or "" = new
  const [ints, setInts] = useState<Record<string, number | null>>({});
  const [bools, setBools] = useState<Record<string, boolean>>({});

  const catalogueQuery = useQuery({
    queryKey: ["platform-entitlement-catalogue"],
    queryFn: () => api.get<Record<string, "int" | "bool">>("/platform/entitlements"),
  });
  const catalogue = catalogueQuery.data?.data ?? {};
  const intKeys = Object.keys(catalogue).filter((k) => catalogue[k] === "int");
  const boolKeys = Object.keys(catalogue).filter((k) => catalogue[k] === "bool");

  function loadPlan(code: string) {
    setEditing(code);
    setMessage(null);
    if (!code) {
      form.setFieldsValue(EMPTY_FORM);
      setInts({});
      setBools({});
      return;
    }
    const plan = plans.find((p) => p.code === code);
    if (!plan) return;
    form.setFieldsValue({
      code: plan.code,
      name: plan.name,
      description: plan.description ?? "",
      monthly: plan.prices.monthly?.amount ?? null,
      yearly: plan.prices.yearly?.amount ?? null,
      currency: plan.prices.monthly?.currency ?? plan.prices.yearly?.currency ?? "INR",
      is_active: plan.is_active,
      sort_order: plan.sort_order,
    });
    setInts(
      Object.fromEntries(
        plan.entitlements
          .filter((e) => e.int_value !== null)
          .map((e) => [e.key, e.int_value]),
      ),
    );
    setBools(
      Object.fromEntries(
        plan.entitlements
          .filter((e) => e.bool_value !== null)
          .map((e) => [e.key, e.bool_value === true]),
      ),
    );
  }

  const save = useMutation({
    mutationFn: (values: PlanFormValues) => {
      const prices: Record<string, { amount: number; currency: string }> = {};
      if (values.monthly != null)
        prices.monthly = { amount: Number(values.monthly), currency: values.currency };
      if (values.yearly != null)
        prices.yearly = { amount: Number(values.yearly), currency: values.currency };
      const entitlements = [
        ...intKeys
          .filter((k) => ints[k] !== undefined && ints[k] !== null)
          .map((k) => ({ key: k, int_value: Number(ints[k]) })),
        ...boolKeys.map((k) => ({ key: k, bool_value: bools[k] ?? false })),
      ];
      return api.post("/platform/plans", {
        code: values.code,
        name: values.name,
        description: values.description || null,
        prices,
        entitlements,
        is_active: values.is_active,
        sort_order: Number(values.sort_order) || 0,
      });
    },
    onSuccess: (_data, values) => {
      queryClient.invalidateQueries({ queryKey: ["platform-plans"] });
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      setMessage({ kind: "ok", text: `Plan '${values.code}' saved.` });
    },
    onError: (err) =>
      setMessage({
        kind: "error",
        text: err instanceof ApiError ? err.message : "Failed to save plan",
      }),
  });

  return (
    <Card
      size="small"
      title="Plan editor"
      extra={
        <Select
          aria-label="Plan to edit"
          className="w-52"
          value={editing}
          onChange={(value: string) => loadPlan(value)}
          options={[
            { value: "", label: "+ New plan" },
            ...plans.map((p) => ({ value: p.code, label: `Edit: ${p.name}` })),
          ]}
        />
      }
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={EMPTY_FORM}
        onFinish={(values) => {
          setMessage(null);
          save.mutate(values);
        }}
      >
        <Row gutter={[12, 0]}>
          <Col xs={12} sm={6}>
            <Form.Item
              name="code"
              label="Code"
              rules={[{ required: true, message: "Code is required." }]}
            >
              <Input disabled={editing !== ""} />
            </Form.Item>
          </Col>
          <Col xs={12} sm={6}>
            <Form.Item
              name="name"
              label="Name"
              rules={[{ required: true, message: "Name is required." }]}
            >
              <Input />
            </Form.Item>
          </Col>
          <Col xs={12} sm={6}>
            <Form.Item name="monthly" label="Monthly price (blank = custom)">
              <InputNumber min={0} className="w-full" />
            </Form.Item>
          </Col>
          <Col xs={12} sm={6}>
            <Form.Item name="yearly" label="Yearly price">
              <InputNumber min={0} className="w-full" />
            </Form.Item>
          </Col>
          <Col xs={12} sm={6}>
            <Form.Item
              name="currency"
              label="Currency"
              normalize={(value: string) => value.toUpperCase()}
            >
              <Input maxLength={3} />
            </Form.Item>
          </Col>
          <Col xs={12} sm={6}>
            <Form.Item name="sort_order" label="Sort order">
              <InputNumber className="w-full" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="description" label="Description">
              <Input />
            </Form.Item>
          </Col>
        </Row>

        <Typography.Text type="secondary" className="text-xs font-semibold uppercase">
          Limits (blank = unlimited)
        </Typography.Text>
        <Row gutter={[12, 0]} className="mt-1.5">
          {intKeys.map((key) => (
            <Col key={key} xs={12} sm={8}>
              <Form.Item label={key.replace(/_/g, " ")}>
                <InputNumber
                  min={0}
                  className="w-full"
                  value={ints[key] ?? null}
                  onChange={(v) => setInts((p) => ({ ...p, [key]: v }))}
                />
              </Form.Item>
            </Col>
          ))}
        </Row>

        <Typography.Text type="secondary" className="text-xs font-semibold uppercase">
          Features
        </Typography.Text>
        <Row gutter={[12, 6]} className="mb-4 mt-1.5">
          {boolKeys.map((key) => (
            <Col key={key} xs={12} sm={6}>
              <Checkbox
                checked={bools[key] ?? false}
                onChange={(e) => setBools((p) => ({ ...p, [key]: e.target.checked }))}
              >
                {key.replace(/_/g, " ")}
              </Checkbox>
            </Col>
          ))}
        </Row>

        <Space wrap>
          <Form.Item name="is_active" valuePropName="checked" className="!mb-0">
            <Checkbox>Open for subscription</Checkbox>
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={save.isPending}>
            {editing ? "Save plan" : "Create plan"}
          </Button>
        </Space>

        {message && (
          <Alert
            className="mt-4"
            type={message.kind === "ok" ? "success" : "error"}
            showIcon
            role={message.kind === "error" ? "alert" : undefined}
            message={message.text}
          />
        )}
      </Form>
    </Card>
  );
}
