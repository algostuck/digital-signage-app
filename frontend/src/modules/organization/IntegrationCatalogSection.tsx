import { useQuery } from "@tanstack/react-query";
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
    <div className="mt-8">
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Integration catalog
        </h2>
        <p className="mt-0.5 text-xs text-slate-400">
          Everything the platform connects to, in one place — configure each
          in its section below (locked items need a plan upgrade).
        </p>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {connectors.map((c) => (
            <div
              key={c.key}
              className={`rounded-md border p-3 ${
                c.available ? "border-slate-200" : "border-slate-200 opacity-60"
              }`}
            >
              <div className="flex items-center justify-between">
                <p className="font-medium text-slate-800">{c.name}</p>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    !c.available
                      ? "bg-slate-100 text-slate-500"
                      : c.configured > 0
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {!c.available
                    ? "plan locked"
                    : c.configured > 0
                      ? `${c.configured} configured`
                      : "not configured"}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">{c.description}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
