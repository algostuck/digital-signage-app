import { useMutation } from "@tanstack/react-query";
import { Alert, Button, Divider, Drawer, Form, Input, InputNumber, Select, Space } from "antd";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { timezoneOptions, usePlans, usePlatformFeedback } from "./api";
import { BILLING_CYCLES } from "./types";

interface Values {
  name: string;
  code: string;
  timezone: string;
  owner_full_name: string;
  owner_email: string;
  owner_password?: string;
  plan_code?: string;
  billing_cycle: string;
  trial_days: number;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

/** Onboards a tenant: organization + owner account, optionally with a
 * plan assigned in the same step so the tenant is usable immediately. */
export function TenantCreateDrawer({ open, onClose }: { open: boolean; onClose(): void }) {
  const [form] = Form.useForm<Values>();
  const navigate = useNavigate();
  const feedback = usePlatformFeedback();
  const plans = usePlans();
  const codeTouched = Form.useWatch("code", form);

  const create = useMutation({
    mutationFn: async (values: Values) => {
      const created = await api.post<{ id: string; name: string }>("/platform/tenants", {
        name: values.name.trim(),
        code: values.code.trim(),
        timezone: values.timezone,
        owner_email: values.owner_email.trim(),
        owner_full_name: values.owner_full_name.trim(),
        owner_password: values.owner_password || null,
      });
      const id = created.data!.id;
      if (values.plan_code) {
        await api.post(`/platform/tenants/${id}/subscription`, {
          plan_code: values.plan_code,
          billing_cycle: values.billing_cycle,
          trial_days: values.trial_days ?? 0,
        });
      }
      return id;
    },
    onSuccess: (id, values) => {
      feedback.done(`${values.name} created.`);
      form.resetFields();
      onClose();
      navigate(`/platform/tenants/${id}`);
    },
    onError: feedback.onError,
  });

  return (
    <Drawer
      title="New tenant"
      open={open}
      onClose={onClose}
      size={520}
      destroyOnHidden
      footer={
        <Space className="w-full justify-end">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="primary" loading={create.isPending} onClick={() => form.submit()}>
            Create tenant
          </Button>
        </Space>
      }
    >
      <Form
        form={form}
        layout="vertical"
        requiredMark="optional"
        initialValues={{ timezone: "UTC", billing_cycle: "monthly", trial_days: 0 }}
        onFinish={(values) => create.mutate(values)}
        onValuesChange={(changed: Partial<Values>) => {
          // Suggest a code from the name until the operator edits it.
          if (changed.name !== undefined && !codeTouched) {
            form.setFieldValue("code", slugify(changed.name));
          }
        }}
      >
        <Divider titlePlacement="start" plain>
          Organization
        </Divider>
        <Form.Item
          name="name"
          label="Organization name"
          rules={[{ required: true, message: "Enter the organization name." }]}
        >
          <Input autoFocus maxLength={200} />
        </Form.Item>
        <Form.Item
          name="code"
          label="Code"
          extra="Lowercase letters, digits and hyphens. Used in URLs and the API; it cannot be changed later."
          rules={[
            { required: true, message: "Enter a code." },
            { pattern: /^[a-z0-9][a-z0-9-]*$/, message: "Lowercase letters, digits and hyphens only." },
          ]}
        >
          <Input maxLength={50} />
        </Form.Item>
        <Form.Item name="timezone" label="Timezone" rules={[{ required: true }]}>
          <Select showSearch optionFilterProp="label" options={timezoneOptions()} />
        </Form.Item>

        <Divider titlePlacement="start" plain>
          Owner account
        </Divider>
        <Form.Item
          name="owner_full_name"
          label="Full name"
          rules={[{ required: true, message: "Enter the owner's name." }]}
        >
          <Input maxLength={200} />
        </Form.Item>
        <Form.Item
          name="owner_email"
          label="E-mail"
          rules={[
            { required: true, message: "Enter the owner's e-mail." },
            { type: "email", message: "Enter a valid e-mail address." },
          ]}
        >
          <Input type="email" />
        </Form.Item>
        <Form.Item
          name="owner_password"
          label="Initial password"
          extra="Leave blank to send an invitation instead."
          rules={[{ min: 8, message: "Use at least 8 characters." }]}
        >
          <Input.Password autoComplete="new-password" />
        </Form.Item>

        <Divider titlePlacement="start" plain>
          Subscription
        </Divider>
        <Alert
          type="info"
          showIcon
          className="mb-4"
          message="Without a plan the tenant runs in legacy mode with no limits. Assign one now, or later from the tenant page."
        />
        <Form.Item name="plan_code" label="Plan">
          <Select
            allowClear
            placeholder="No plan yet"
            loading={plans.isLoading}
            options={(plans.data?.data ?? [])
              .filter((p) => p.is_active)
              .map((p) => ({ value: p.code, label: p.name }))}
          />
        </Form.Item>
        <Form.Item noStyle shouldUpdate={(a, b) => a.plan_code !== b.plan_code}>
          {({ getFieldValue }) =>
            getFieldValue("plan_code") ? (
              <Space size="middle" align="start">
                <Form.Item name="billing_cycle" label="Billing cycle">
                  <Select
                    className="w-36"
                    options={BILLING_CYCLES.map((c) => ({ value: c, label: c }))}
                  />
                </Form.Item>
                <Form.Item name="trial_days" label="Trial days">
                  <InputNumber min={0} max={365} className="w-28" />
                </Form.Item>
              </Space>
            ) : null
          }
        </Form.Item>
      </Form>
    </Drawer>
  );
}
