import { CloudServerOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Result, Space, Typography } from "antd";
import { ToneTag } from "../../components/ui/ToneTag";
import { toneOf } from "../../components/ui/tone";
import { useState } from "react";
import { PageHeader } from "../../components/ui/PageHeader";
import { LoadingState } from "../../components/ui/states";
import { api, ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface ApiVersionRow {
  version: string;
  lifecycle_state: string;
  sunset_at: string | null;
  released_at: string | null;
  changelog: { date: string; note: string }[];
}

interface OpenApiMeta {
  openapi_url: string | null;
  docs_url: string | null;
  products: { name: string; description: string | null; versions: ApiVersionRow[] }[];
}

interface SandboxInfo {
  organization_id: string;
  name: string;
  code: string;
  enrollment_key: string;
  devices: number;
  created?: boolean;
}

interface SimulatedDevice {
  device_id: string;
  serial_no: string;
  device_token: string;
  heartbeat_url: string;
  manifest_url: string;
}

const LIFECYCLE_COLOR: Record<string, string> = {
  current: "success",
  preview: "processing",
  deprecated: "warning",
  sunset: "error",
};

/** P3-23 Developer Portal: versioned contracts + changelog, sandbox tenant,
 * device simulator. API keys stay in Settings → Integrations (2H). */
export function DeveloperPage() {
  const { hasPermission } = useAuth();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [simulated, setSimulated] = useState<SimulatedDevice | null>(null);

  const metaQuery = useQuery({
    queryKey: ["developer-openapi"],
    queryFn: () => api.get<OpenApiMeta>("/developer/openapi"),
    retry: false,
  });
  const sandboxQuery = useQuery({
    queryKey: ["developer-sandbox"],
    queryFn: () => api.get<SandboxInfo | null>("/developer/sandbox"),
    retry: false,
    enabled: metaQuery.isSuccess,
  });

  const onError = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Action failed");
  const provision = useMutation({
    mutationFn: () => api.post<SandboxInfo>("/developer/sandbox", {}),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["developer-sandbox"] });
      queryClient.invalidateQueries({ queryKey: ["memberships"] });
    },
    onError,
  });
  const simulate = useMutation({
    mutationFn: () =>
      api.post<SimulatedDevice>("/developer/sandbox/simulate-device", {}),
    onSuccess: (envelope) => {
      setError(null);
      setSimulated(envelope.data!);
      queryClient.invalidateQueries({ queryKey: ["developer-sandbox"] });
    },
    onError,
  });

  if (!hasPermission("api_keys.manage"))
    return (
      <Result
        status="403"
        title="Developer Portal unavailable"
        subTitle="Requires the api_keys.manage permission."
      />
    );
  if (metaQuery.isLoading) return <LoadingState rows={6} />;
  if (metaQuery.isError)
    return (
      <Alert
        type="warning"
        showIcon
        role="alert"
        message={
          metaQuery.error instanceof ApiError
            ? metaQuery.error.message
            : "Developer portal unavailable."
        }
      />
    );

  const meta = metaQuery.data?.data;
  const sandbox = sandboxQuery.data?.data ?? null;

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Developer Portal"
        description="Versioned API contracts, sandbox tenant and device simulator. API keys are managed in Settings → Integrations."
      />
      <Space orientation="vertical" size="large" className="w-full">
        {meta?.docs_url && (
          <Typography.Text>
            Interactive docs:{" "}
            <Typography.Link href={meta.docs_url} target="_blank" rel="noreferrer">
              {meta.docs_url}
            </Typography.Link>{" "}
            · OpenAPI:{" "}
            <Typography.Link href={meta.openapi_url ?? "#"} target="_blank" rel="noreferrer">
              {meta.openapi_url}
            </Typography.Link>
          </Typography.Text>
        )}

        <Card size="small" title="Sandbox tenant">
          <Typography.Paragraph type="secondary" className="!mb-2 text-xs">
            An isolated test organization — build and break freely without
            touching production content or devices. You get an owner membership,
            so it appears in the tenant switcher in the header.
          </Typography.Paragraph>
          {sandbox == null ? (
            <Button
              type="primary"
              icon={<CloudServerOutlined />}
              loading={provision.isPending}
              onClick={() => provision.mutate()}
            >
              Provision sandbox
            </Button>
          ) : (
            <Space orientation="vertical" size="small" className="w-full">
              <Typography.Text>
                <Typography.Text strong>{sandbox.name}</Typography.Text>{" "}
                <Typography.Text code className="text-xs">
                  {sandbox.code}
                </Typography.Text>{" "}
                · {sandbox.devices} device{sandbox.devices === 1 ? "" : "s"}
              </Typography.Text>
              <Typography.Text type="secondary" className="text-xs">
                Enrollment key (for player registration):{" "}
                <Typography.Text code copyable>
                  {sandbox.enrollment_key}
                </Typography.Text>
              </Typography.Text>
              <Button
                icon={<PlayCircleOutlined />}
                loading={simulate.isPending}
                onClick={() => simulate.mutate()}
              >
                Simulate a device
              </Button>
              {simulated && (
                <Alert
                  type="warning"
                  showIcon
                  message={`Device ${simulated.serial_no} enrolled — token shown only once:`}
                  description={
                    <Space orientation="vertical" size={4}>
                      <Typography.Text code copyable className="break-all text-xs">
                        {simulated.device_token}
                      </Typography.Text>
                      <Typography.Text type="secondary" className="text-xs">
                        POST {simulated.heartbeat_url} · GET {simulated.manifest_url}
                        {"  "}(header X-Device-Token)
                      </Typography.Text>
                    </Space>
                  }
                />
              )}
            </Space>
          )}
        </Card>

        {(meta?.products ?? []).map((product) => (
          <Card size="small" key={product.name} title={product.name}>
            {product.description && (
              <Typography.Paragraph type="secondary" className="!mb-3 text-xs">
                {product.description}
              </Typography.Paragraph>
            )}
            <Space orientation="vertical" size="small" className="w-full">
              {product.versions.map((v) => (
                <Card key={v.version} type="inner" size="small">
                  <Space wrap size="small">
                    <Typography.Text strong code>
                      {v.version}
                    </Typography.Text>
                    <ToneTag tone={toneOf(LIFECYCLE_COLOR[v.lifecycle_state] ?? "default")}
                    >
                      {v.lifecycle_state}
                    </ToneTag>
                    {v.sunset_at && (
                      <Typography.Text type="danger" className="text-xs">
                        sunset {new Date(v.sunset_at).toLocaleDateString()}
                      </Typography.Text>
                    )}
                  </Space>
                  <ul className="mb-0 mt-2 list-none space-y-1 p-0">
                    {v.changelog.map((entry, i) => (
                      <li key={i}>
                        <Typography.Text type="secondary" className="text-xs">
                          {entry.date}
                        </Typography.Text>{" "}
                        <Typography.Text>{entry.note}</Typography.Text>
                      </li>
                    ))}
                  </ul>
                </Card>
              ))}
            </Space>
          </Card>
        ))}

        {error && <Alert type="error" showIcon role="alert" message={error} />}
      </Space>
    </div>
  );
}
