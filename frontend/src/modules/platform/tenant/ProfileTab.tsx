
import { useMutation } from "@tanstack/react-query";
import { Button, Card, Form, Input, Select, Space } from "antd";

import { useEffect, useState } from "react";

import { api } from "../../../lib/api";
import { timezoneOptions, usePlatformFeedback } from "../api";

import { type TenantDetail } from "../types";

interface ProfileValues {
  name: string;
  timezone: string;
  region: string;
}

export function ProfileTab({ tenant }: { tenant: TenantDetail }) {
  const feedback = usePlatformFeedback();
  const [form] = Form.useForm<ProfileValues>();
  const [dirty, setDirty] = useState(false);

  const reset = () => {
    form.setFieldsValue({ name: tenant.name, timezone: tenant.timezone, region: tenant.region });
    setDirty(false);
  };
  useEffect(reset, [tenant, form]);

  const save = useMutation({
    mutationFn: (values: ProfileValues) =>
      api.patch(`/platform/tenants/${tenant.id}`, {
        name: values.name.trim(),
        timezone: values.timezone,
        region: values.region.trim(),
      }),
    onSuccess: () => {
      feedback.done("Tenant profile saved.");
      setDirty(false);
    },
    onError: feedback.onError,
  });

  return (
    <Card size="small">
      <Form
        form={form}
        layout="vertical"
        requiredMark="optional"
        className="max-w-xl"
        onValuesChange={() => setDirty(true)}
        onFinish={(values) => save.mutate(values)}
      >
        <Form.Item name="name" label="Organization name" rules={[{ required: true, message: "Enter a name." }]}>
          <Input maxLength={200} />
        </Form.Item>
        <Form.Item label="Code" extra="Permanent; used in URLs and the API.">
          <Input value={tenant.code} disabled />
        </Form.Item>
        <Form.Item name="timezone" label="Timezone" rules={[{ required: true }]}>
          <Select showSearch optionFilterProp="label" options={timezoneOptions()} />
        </Form.Item>
        <Form.Item
          name="region"
          label="Data region"
          extra="Residency label shown to the tenant and used for reporting. Moving data is a deployment operation, not this field."
          rules={[{ required: true, message: "Enter a region." }]}
        >
          <Input maxLength={50} />
        </Form.Item>
        <Space>
          <Button type="primary" htmlType="submit" loading={save.isPending} disabled={!dirty}>
            Save changes
          </Button>
          {dirty && <Button onClick={reset}>Discard</Button>}
        </Space>
      </Form>
    </Card>
  );
}

// ---------------------------------------------------------------------------
