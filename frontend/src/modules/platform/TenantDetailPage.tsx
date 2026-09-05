import { DownOutlined } from "@ant-design/icons";
import { useMutation } from "@tanstack/react-query";
import { App, Button, Dropdown, Tabs } from "antd";

import { useParams } from "react-router-dom";

import { PageHeader } from "@/design-system";
import { ErrorState, LoadingState } from "@/design-system";
import { StatusBadge } from "@/design-system";
import { api } from "../../lib/api";
import { formatDate, usePlatformFeedback, useTenant } from "./api";
import { PlatformGuard, PLATFORM_CRUMB } from "./PlatformGuard";
import { InvoicesTab } from "./tenant/InvoicesTab";
import { ProfileTab } from "./tenant/ProfileTab";
import { QuotasTab } from "./tenant/QuotasTab";
import { SubscriptionTab } from "./tenant/SubscriptionTab";

import { type TenantDetail } from "./types";

/** The tenant workspace: subscription, usage, invoices and profile, each
 * on its own tab with its own save — no page-wide form. */
export function TenantDetailPage() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const tenant = useTenant(tenantId);

  return (
    <PlatformGuard>
      {tenant.isLoading ? (
        <LoadingState rows={10} />
      ) : tenant.error || !tenant.data?.data ? (
        <ErrorState
          title="Tenant unavailable"
          description="It may have been removed, or the service did not respond."
          onRetry={() => void tenant.refetch()}
        />
      ) : (
        <TenantWorkspace tenant={tenant.data.data} />
      )}
    </PlatformGuard>
  );
}

function TenantWorkspace({ tenant }: { tenant: TenantDetail }) {
  const feedback = usePlatformFeedback();
  const { modal } = App.useApp();

  const setStatus = useMutation({
    mutationFn: (status: string) => api.patch(`/platform/tenants/${tenant.id}/status`, { status }),
    onSuccess: (_d, status) => feedback.done(`${tenant.name} is now ${status}.`),
    onError: feedback.onError,
  });

  const lifecycle: Record<string, { label: string; title: string; body: string; danger?: boolean }> = {
    active: {
      label: "Reactivate tenant",
      title: `Reactivate ${tenant.name}?`,
      body: "Users can sign in again and the API accepts their requests.",
    },
    suspended: {
      label: "Suspend tenant",
      title: `Suspend ${tenant.name}?`,
      body: "Every user is locked out and the API refuses their tokens. Screens keep playing cached content — a suspension never blanks a display.",
      danger: true,
    },
    archived: {
      label: "Archive tenant",
      title: `Archive ${tenant.name}?`,
      body: "The tenant is retired from the platform. Data is retained; nobody can sign in.",
      danger: true,
    },
  };

  const lifecycleMenu = Object.entries(lifecycle)
    .filter(([status]) => status !== tenant.status)
    .map(([status, action]) => ({
      key: status,
      label: action.label,
      danger: action.danger,
      onClick: () =>
        modal.confirm({
          title: action.title,
          content: action.body,
          okText: action.label,
          okButtonProps: { danger: action.danger },
          onOk: () => setStatus.mutateAsync(status),
        }),
    }));

  return (
    <>
      <PageHeader
        title={tenant.name}
        breadcrumbs={[PLATFORM_CRUMB, { label: "Tenants", to: "/platform/tenants" }, { label: tenant.name }]}
        description={`${tenant.code} · created ${formatDate(tenant.created_at)}`}
        actions={
          <>
            <StatusBadge status={tenant.status} />
            <Dropdown menu={{ items: lifecycleMenu }} trigger={["click"]}>
              <Button loading={setStatus.isPending}>
                Lifecycle <DownOutlined />
              </Button>
            </Dropdown>
          </>
        }
      />

      <Tabs
        defaultActiveKey="subscription"
        items={[
          { key: "subscription", label: "Subscription", children: <SubscriptionTab tenant={tenant} /> },
          { key: "usage", label: "Usage & quotas", children: <QuotasTab tenant={tenant} /> },
          { key: "invoices", label: "Invoices", children: <InvoicesTab tenant={tenant} /> },
          { key: "profile", label: "Profile", children: <ProfileTab tenant={tenant} /> },
        ]}
      />
    </>
  );
}

