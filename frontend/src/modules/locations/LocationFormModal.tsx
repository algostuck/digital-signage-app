import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Form, Input, Modal, Select } from "antd";
import { useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { LocationDetail, LocationType } from "./types";

interface Props {
  existing?: LocationDetail;
  parentId?: string | null;
  parentName?: string | null;
  onClose: () => void;
  onSaved: (id: string) => void;
}

interface FormValues {
  name: string;
  code?: string;
  type_id?: string;
  address?: string;
  timezone?: string;
}

export function LocationFormModal({ existing, parentId, parentName, onClose, onSaved }: Props) {
  const [form] = Form.useForm<FormValues>();
  const [error, setError] = useState<string | null>(null);

  const typesQuery = useQuery({
    queryKey: ["location-types"],
    queryFn: () => api.get<LocationType[]>("/location-types"),
  });

  const save = useMutation({
    mutationFn: (values: FormValues) => {
      const body = {
        name: values.name,
        code: values.code || null,
        type_id: values.type_id || null,
        address: values.address || null,
        timezone: values.timezone || null,
      };
      return existing
        ? api.patch<LocationDetail>(`/locations/${existing.id}`, body)
        : api.post<LocationDetail>("/locations", { ...body, parent_id: parentId ?? null });
    },
    onSuccess: (envelope) => onSaved(envelope.data!.id),
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Failed to save location"),
  });

  const title = existing
    ? `Edit location: ${existing.name}`
    : parentName
      ? `Add child under ${parentName}`
      : "Add root location";

  return (
    <Modal
      title={title}
      open
      onCancel={onClose}
      okText={existing ? "Save changes" : "Create location"}
      confirmLoading={save.isPending}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {error && <Alert type="error" message={error} showIcon className="mb-4" role="alert" />}
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          name: existing?.name ?? "",
          code: existing?.code ?? "",
          type_id: existing?.type?.id || undefined,
          address: existing?.address ?? "",
          timezone: existing?.timezone ?? "",
        }}
        onFinish={(values) => {
          setError(null);
          save.mutate(values);
        }}
      >
        <Form.Item
          name="name"
          label="Name"
          rules={[{ required: true, message: "Name is required." }]}
        >
          <Input autoFocus />
        </Form.Item>
        <Form.Item name="code" label="Code (unique among siblings, optional)">
          <Input />
        </Form.Item>
        <Form.Item name="type_id" label="Type">
          <Select
            allowClear
            placeholder="— none —"
            options={(typesQuery.data?.data ?? []).map((t) => ({
              value: t.id,
              label: t.name,
            }))}
          />
        </Form.Item>
        <Form.Item name="address" label="Address (optional)">
          <Input />
        </Form.Item>
        <Form.Item name="timezone" label="Timezone (IANA, optional — inherits when empty)">
          <Input placeholder="e.g. Asia/Kolkata" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
