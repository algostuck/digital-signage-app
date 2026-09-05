import { useQuery } from "@tanstack/react-query";
import { Card, Flex, List, Typography } from "antd";
import { ToneTag } from "../../components/ui/ToneTag";
import { toneOf } from "../../components/ui/tone";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface ConnectorRow {
  key: string;
  name: string;
  description: string;
  configured: number;
  available: boolean;
  surface: string;
}

/** P3-19 Integration Catalog: one consolidated view over the concrete
 * integration stores (webhooks, event bus, data sources, keys, SSO, SMTP). */
export function IntegrationCatalogSection() {
  const { hasPermission } = useAuth();
  const canView = hasPermission("webhooks.manage");
  const query = useQuery({
    queryKey: ["connectors"],
    queryFn: () => api.get<ConnectorRow[]>("/connectors"),
    enabled: canView,
  });
  if (!canView) return null;
  const connectors = query.data?.data ?? [];

  return (
    <Card size="small" title="Integration catalog" loading={query.isLoading}>
      <Typography.Paragraph type="secondary" className="!mb-3">
        Everything the platform connects to, in one place — configure each
        in its section below (locked items need a plan upgrade).
      </Typography.Paragraph>
      <List
        grid={{ gutter: 12, xs: 1, sm: 2, lg: 3 }}
        dataSource={connectors}
        renderItem={(c) => (
          <List.Item className="!mb-3">
            <Card size="small">
              <Flex align="center" justify="space-between" gap="small">
                <Typography.Text strong disabled={!c.available}>
                  {c.name}
                </Typography.Text>
                <ToneTag tone={toneOf(!c.available ? "default" : c.configured > 0 ? "success" : "default")}
                >
                  {!c.available
                    ? "plan locked"
                    : c.configured > 0
                      ? `${c.configured} configured`
                      : "not configured"}
                </ToneTag>
              </Flex>
              <Typography.Paragraph type="secondary" className="!mb-0 mt-1 text-xs">
                {c.description}
              </Typography.Paragraph>
            </Card>
          </List.Item>
        )}
      />
    </Card>
  );
}
