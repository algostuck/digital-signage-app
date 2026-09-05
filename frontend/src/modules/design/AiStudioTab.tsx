import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Form, Input, InputNumber, Row, Select, Space, Tooltip, Typography, type TableProps } from "antd";
import { ToneTag } from "@/design-system";
import { DataTable } from "@/design-system";
import { toneOf } from "@/design-system";
import { useState } from "react";

import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface AiOutputRow {
  id: string;
  kind: string;
  content: Record<string, unknown>;
  confidence: number;
  fallback: boolean;
  safety_status: string;
  safety_notes: string | null;
}

interface AiRequestRow {
  id: string;
  operation: string;
  provider: string;
  model_ref: string | null;
  template_version: string | null;
  status: string;
  created_at: string | null;
  outputs: AiOutputRow[];
}

const SAFETY_COLOR: Record<string, string> = {
  passed: "success",
  pending: "processing",
  flagged: "warning",
  rejected: "error",
};

const TEXT_TEMPLATES = [
  { value: "headline", label: "Headline (title case, fit)" },
  { value: "shorten", label: "Shorten to length" },
  { value: "cta", label: "Call to action" },
  { value: "tone_formal", label: "Formal tone" },
  { value: "tone_casual", label: "Casual tone" },
];

const LOCALES = ["hi", "bn", "es", "fr", "de"];

const DIMENSIONS = [
  { label: "Landscape 1920×1080", width: 1920, height: 1080 },
  { label: "Portrait 1080×1920", width: 1080, height: 1920 },
  { label: "Banner 3840×720", width: 3840, height: 720 },
  { label: "Square 1080×1080", width: 1080, height: 1080 },
];

function ConfidenceBadge({ output }: { output: AiOutputRow }) {
  const pct = Math.round(output.confidence * 100);
  return (
    <Space size={4} wrap>
      <ToneTag tone={toneOf(SAFETY_COLOR[output.safety_status] ?? "default")}>
        {output.safety_status}
      </ToneTag>
      <Tooltip title="Recommendation confidence (deterministic provider)">
        <ToneTag tone={toneOf(pct >= 80 ? "success" : "warning")}>
          {pct}% confidence
        </ToneTag>
      </Tooltip>
      {output.fallback && <ToneTag tone="default">fallback result</ToneTag>}
    </Space>
  );
}

/** P3-01 AI Content Studio + P3-02 Variant Manager. Every result is a
 * RECOMMENDATION: labeled with provider/model/template version and
 * confidence; guardrail violations are flagged, approval routing goes
 * through the standard Approvals inbox. */
export function AiStudioTab() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<AiRequestRow | null>(null);

  const requestsQuery = useQuery({
    queryKey: ["ai-requests"],
    queryFn: () => api.get<AiRequestRow[]>("/ai/requests?page_size=10"),
    retry: false,
  });

  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "AI request failed");
  const onDone = (envelope: { data?: AiRequestRow | null }) => {
    setError(null);
    setLastResult(envelope.data ?? null);
    queryClient.invalidateQueries({ queryKey: ["ai-requests"] });
  };

  const generateText = useMutation({
    mutationFn: (values: { template: string; text: string; max_chars?: number | null }) =>
      api.post<AiRequestRow>("/ai/generate/text", {
        template: values.template,
        text: values.text,
        max_chars: values.max_chars ?? null,
      }),
    onSuccess: onDone,
    onError,
  });

  const localize = useMutation({
    mutationFn: (values: { text: string; locale: string }) =>
      api.post<AiRequestRow>("/ai/localize", {
        text: values.text,
        target_locale: values.locale,
      }),
    onSuccess: onDone,
    onError,
  });

  const generateCreative = useMutation({
    mutationFn: (values: { headline: string; body?: string; dim: number }) =>
      api.post<AiRequestRow>("/ai/generate/creative", {
        headline: values.headline,
        body: values.body || null,
        width: DIMENSIONS[values.dim].width,
        height: DIMENSIONS[values.dim].height,
      }),
    onSuccess: onDone,
    onError,
  });

  if (requestsQuery.isError)
    return (
      <Alert
        type="warning"
        showIcon
        role="alert"
        message={
          requestsQuery.error instanceof ApiError
            ? requestsQuery.error.message
            : "AI studio unavailable."
        }
      />
    );

  const canCreate = hasPermission("content.create");
  const canCreative = hasPermission("layouts.manage");
  const requests = requestsQuery.data?.data ?? [];

  const activityColumns: TableProps<AiRequestRow>["columns"] = [
    { title: "Operation", dataIndex: "operation" },
    {
      title: "Template",
      dataIndex: "template_version",
      render: (template_version: string | null) => (
        <Typography.Text code className="text-xs">
          {template_version}
        </Typography.Text>
      ),
    },
    {
      title: "Result",
      render: (_, r) => (
        <Typography.Text type="secondary" ellipsis className="max-w-md font-mono text-xs">
          {r.outputs[0]
            ? String(r.outputs[0].content.text ?? r.outputs[0].content.headline ?? "")
            : "—"}
        </Typography.Text>
      ),
    },
    {
      title: "Safety / confidence",
      render: (_, r) => (r.outputs[0] ? <ConfidenceBadge output={r.outputs[0]} /> : null),
    },
    {
      title: "When",
      dataIndex: "created_at",
      render: (created_at: string | null) =>
        created_at ? new Date(created_at).toLocaleString() : "—",
    },
  ];

  return (
    <Space orientation="vertical" size="medium" className="w-full">
      <Typography.Text type="secondary" className="text-xs">
        Results are <strong>recommendations</strong> from the configured AI
        provider (currently deterministic rules — no external model). Each
        output records provider, template version and confidence; your
        organization's guardrails and approval policy apply.
      </Typography.Text>

      <Row gutter={[16, 16]}>
        {canCreate && (
          <Col xs={24} lg={8}>
            <Card size="small" title="Copy assistant" className="h-full">
              <Form
                layout="vertical"
                initialValues={{ template: "headline" }}
                onFinish={(values) => {
                  setError(null);
                  generateText.mutate(values);
                }}
              >
                <Form.Item name="template" label="Template">
                  <Select aria-label="Text template" options={TEXT_TEMPLATES} />
                </Form.Item>
                <Form.Item
                  name="text"
                  label="Copy"
                  rules={[{ required: true, message: "Enter the copy to work on." }]}
                >
                  <Input.TextArea rows={3} placeholder="Your copy…" />
                </Form.Item>
                <Form.Item name="max_chars" label="Max characters (optional)">
                  <InputNumber min={8} className="w-full" />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={generateText.isPending}>
                  Generate
                </Button>
              </Form>
            </Card>
          </Col>
        )}

        {canCreate && (
          <Col xs={24} lg={8}>
            <Card size="small" title="Localize" className="h-full">
              <Form
                layout="vertical"
                initialValues={{ locale: "es" }}
                onFinish={(values) => {
                  setError(null);
                  localize.mutate(values);
                }}
              >
                <Form.Item
                  name="text"
                  label="Text"
                  rules={[{ required: true, message: "Enter the text to localize." }]}
                >
                  <Input.TextArea rows={3} placeholder="Text with {{placeholders}} preserved…" />
                </Form.Item>
                <Form.Item name="locale" label="Target locale">
                  <Select
                    aria-label="Target locale"
                    options={LOCALES.map((l) => ({ value: l, label: l }))}
                  />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={localize.isPending}>
                  Localize
                </Button>
              </Form>
            </Card>
          </Col>
        )}

        {canCreative && (
          <Col xs={24} lg={8}>
            <Card size="small" title="Creative variant" className="h-full">
              <Form
                layout="vertical"
                initialValues={{ dim: 0 }}
                onFinish={(values) => {
                  setError(null);
                  generateCreative.mutate(values);
                }}
              >
                <Form.Item
                  name="headline"
                  label="Headline"
                  rules={[{ required: true, message: "Enter a headline." }]}
                >
                  <Input placeholder="Headline" />
                </Form.Item>
                <Form.Item name="body" label="Body (optional)">
                  <Input placeholder="Body (optional)" />
                </Form.Item>
                <Form.Item name="dim" label="Dimensions">
                  <Select
                    aria-label="Dimensions"
                    options={DIMENSIONS.map((d, i) => ({ value: i, label: d.label }))}
                  />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={generateCreative.isPending}>
                  Generate variant
                </Button>
              </Form>
            </Card>
          </Col>
        )}
      </Row>

      {error && <Alert type="error" message={error} showIcon role="alert" />}

      {lastResult && (
        <Card size="small" title="Latest result">
          {lastResult.outputs.map((output) => (
            <Space key={output.id} orientation="vertical" size="small" className="w-full">
              <ConfidenceBadge output={output} />
              <Typography.Paragraph className="!mb-0">
                <pre className="max-h-48 overflow-auto text-xs">
                  {JSON.stringify(output.content, null, 2)}
                </pre>
              </Typography.Paragraph>
              {output.safety_status === "pending" && (
                <Alert
                  type="info"
                  showIcon
                  message="Awaiting approval — see the Approvals inbox."
                />
              )}
              {output.safety_notes && output.safety_status === "flagged" && (
                <Alert type="warning" showIcon message={`Guardrail: ${output.safety_notes}`} />
              )}
            </Space>
          ))}
          <Typography.Paragraph type="secondary" className="!mb-0 mt-2 text-xs">
            {lastResult.provider} · {lastResult.model_ref} ·{" "}
            {lastResult.template_version}
          </Typography.Paragraph>
        </Card>
      )}

      <Card size="small" title="Recent AI activity (explainability trail)">
        <DataTable<AiRequestRow>
          rowKey="id"
          columns={activityColumns}
          dataSource={requests}
          loading={requestsQuery.isLoading}
          pagination={false}
          emptyTitle="No AI activity yet."
        />
      </Card>
    </Space>
  );
}
