import { useMutation } from "@tanstack/react-query";
import { Alert, Form, Input, Modal, Select, Typography } from "antd";
import { api } from "../../lib/api";
import { formatMoney, usePlatformFeedback } from "./api";
import { PROVIDERS, type InvoiceRow } from "./types";

interface Values {
  provider: string;
  provider_ref?: string;
}

/** Marks an issued invoice as paid. Used from the tenant page and from
 * the platform-wide ledger, so the consequence text lives in one place. */
export function RecordPaymentModal({
  tenantId,
  tenantName,
  invoice,
  onClose,
}: {
  tenantId: string;
  tenantName?: string;
  invoice: InvoiceRow | null;
  onClose(): void;
}) {
  const [form] = Form.useForm<Values>();
  const feedback = usePlatformFeedback();

  const record = useMutation({
    mutationFn: (values: Values) =>
      api.post(`/platform/tenants/${tenantId}/payments`, {
        invoice_id: invoice!.id,
        provider: values.provider,
        provider_ref: values.provider_ref?.trim() || null,
      }),
    onSuccess: () => {
      feedback.done(`Payment recorded for ${invoice?.number}.`);
      form.resetFields();
      onClose();
    },
    onError: feedback.onError,
  });

  return (
    <Modal
      title="Record payment"
      open={invoice != null}
      onCancel={onClose}
      okText="Record payment"
      confirmLoading={record.isPending}
      onOk={() => form.submit()}
      destroyOnHidden
    >
      {invoice && (
        <>
          <Typography.Paragraph>
            <Typography.Text strong>{invoice.number}</Typography.Text>
            {tenantName ? ` · ${tenantName}` : ""} ·{" "}
            <Typography.Text strong>{formatMoney(invoice.amount, invoice.currency)}</Typography.Text>
          </Typography.Paragraph>
          <Alert
            type="info"
            showIcon
            className="mb-4"
            message="The invoice is marked paid immediately. If the subscription is past due, in its grace period or suspended for non-payment, it reactivates at the same time."
          />
          <Form
            form={form}
            layout="vertical"
            initialValues={{ provider: "manual" }}
            onFinish={(values) => record.mutate(values)}
          >
            <Form.Item name="provider" label="Received via" rules={[{ required: true }]}>
              <Select options={PROVIDERS.map((p) => ({ value: p, label: p }))} />
            </Form.Item>
            <Form.Item
              name="provider_ref"
              label="Reference"
              extra="Bank transfer ID, gateway payment ID or receipt number — shown on the audit trail."
            >
              <Input maxLength={200} placeholder="e.g. UTR / pay_… / receipt no." />
            </Form.Item>
          </Form>
        </>
      )}
    </Modal>
  );
}
