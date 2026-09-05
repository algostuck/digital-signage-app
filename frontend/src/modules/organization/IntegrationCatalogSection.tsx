import { useQuery } from "@tanstack/react-query";
import { Card, Col, Flex, Row, Typography } from "antd";
import { ToneTag } from "@/design-system";
import { SectionCard } from "@/design-system";
import { toneOf } from "@/design-system";
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
    <SectionCard title="Integration catalog" loading={query.isLoading}>
      <Typography.Paragraph type="secondary" className="!mb-3">
        Everything the platform connects to, in one place — configure each
        in its section below (locked items need a plan upgrade).
      </Typography.Paragraph>
      <Row gutter={[12, 12]}>
        {connectors.map((c) => (
          <Col key={c.key} xs={24} sm={12} lg={8}>
            <Card size="small" style={{ height: "100%" }}>
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
          </Col>
        ))}
      </Row>
    </SectionCard>
  );
}
