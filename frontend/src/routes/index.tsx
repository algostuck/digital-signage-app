import { Skeleton } from "antd";
import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { ExceptionPage } from "@/design-system";
import { AppLayout } from "../components/layout/AppLayout";
import { ForgotPasswordPage } from "../modules/auth/ForgotPasswordPage";
import { LoginPage } from "../modules/auth/LoginPage";
import { ProtectedRoute } from "./ProtectedRoute";

const DashboardPage = lazy(() => import("../modules/dashboard/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const ContentPage = lazy(() => import("../modules/content/ContentPage").then((m) => ({ default: m.ContentPage })));
const LayoutsPage = lazy(() => import("../modules/design/LayoutsPage").then((m) => ({ default: m.LayoutsPage })));
const DesignerPage = lazy(() => import("../modules/design/DesignerPage").then((m) => ({ default: m.DesignerPage })));
const PlaylistsPage = lazy(() => import("../modules/playlists/PlaylistsPage").then((m) => ({ default: m.PlaylistsPage })));
const PlaylistEditorPage = lazy(() => import("../modules/playlists/PlaylistEditorPage").then((m) => ({ default: m.PlaylistEditorPage })));
const CampaignsPage = lazy(() => import("../modules/campaigns/CampaignsPage").then((m) => ({ default: m.CampaignsPage })));
const ApprovalsPage = lazy(() => import("../modules/approvals/ApprovalsPage").then((m) => ({ default: m.ApprovalsPage })));
const SchedulesPage = lazy(() => import("../modules/campaigns/SchedulesPage").then((m) => ({ default: m.SchedulesPage })));
const DeploymentsPage = lazy(() => import("../modules/campaigns/DeploymentsPage").then((m) => ({ default: m.DeploymentsPage })));
const DevicesPage = lazy(() => import("../modules/devices/DevicesPage").then((m) => ({ default: m.DevicesPage })));
const LocationsPage = lazy(() => import("../modules/locations/LocationsPage").then((m) => ({ default: m.LocationsPage })));
const ReleasesPage = lazy(() => import("../modules/releases/ReleasesPage").then((m) => ({ default: m.ReleasesPage })));
const MonitoringPage = lazy(() => import("../modules/monitoring/MonitoringPage").then((m) => ({ default: m.MonitoringPage })));
const ReportsPage = lazy(() => import("../modules/ops/ReportsPage").then((m) => ({ default: m.ReportsPage })));
const UsersRolesPage = lazy(() => import("../modules/users/UsersRolesPage").then((m) => ({ default: m.UsersRolesPage })));
const NotificationsPage = lazy(() => import("../modules/ops/NotificationsPage").then((m) => ({ default: m.NotificationsPage })));
const AuditPage = lazy(() => import("../modules/ops/AuditPage").then((m) => ({ default: m.AuditPage })));
const OrganizationSettingsPage = lazy(() => import("../modules/organization/OrganizationSettingsPage").then((m) => ({ default: m.OrganizationSettingsPage })));
const SimulatorPage = lazy(() => import("../modules/simulator/SimulatorPage").then((m) => ({ default: m.SimulatorPage })));
const DeveloperPage = lazy(() => import("../modules/developer/DeveloperPage").then((m) => ({ default: m.DeveloperPage })));
const AdsPage = lazy(() => import("../modules/ads/AdsPage").then((m) => ({ default: m.AdsPage })));
const SecurityPage = lazy(() => import("../modules/security/SecurityPage").then((m) => ({ default: m.SecurityPage })));
const PlatformOverviewPage = lazy(() => import("../modules/platform/PlatformOverviewPage").then((m) => ({ default: m.PlatformOverviewPage })));
const TenantsPage = lazy(() => import("../modules/platform/TenantsPage").then((m) => ({ default: m.TenantsPage })));
const TenantDetailPage = lazy(() => import("../modules/platform/TenantDetailPage").then((m) => ({ default: m.TenantDetailPage })));
const PlansPage = lazy(() => import("../modules/platform/PlansPage").then((m) => ({ default: m.PlansPage })));
const PlanRequestsPage = lazy(() => import("../modules/platform/PlanRequestsPage").then((m) => ({ default: m.PlanRequestsPage })));
const InvoicesPage = lazy(() => import("../modules/platform/InvoicesPage").then((m) => ({ default: m.InvoicesPage })));

function withSuspense(node: ReactNode) {
  return (
    <Suspense fallback={<Skeleton active paragraph={{ rows: 6 }} className="p-2" />}>
      {node}
    </Suspense>
  );
}

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: "/",
        element: <AppLayout />,
        errorElement: <ExceptionPage status={500} />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: "dashboard", element: withSuspense(<DashboardPage />) },
          { path: "content", element: withSuspense(<ContentPage />) },
          { path: "design", element: withSuspense(<LayoutsPage />) },
          { path: "design/:layoutId", element: withSuspense(<DesignerPage />) },
          { path: "playlists", element: withSuspense(<PlaylistsPage />) },
          { path: "playlists/:playlistId", element: withSuspense(<PlaylistEditorPage />) },
          { path: "campaigns", element: withSuspense(<CampaignsPage />) },
          { path: "approvals", element: withSuspense(<ApprovalsPage />) },
          { path: "schedules", element: withSuspense(<SchedulesPage />) },
          { path: "deployments", element: withSuspense(<DeploymentsPage />) },
          { path: "devices", element: withSuspense(<DevicesPage />) },
          { path: "locations", element: withSuspense(<LocationsPage />) },
          { path: "releases", element: withSuspense(<ReleasesPage />) },
          { path: "simulator", element: withSuspense(<SimulatorPage />) },
          { path: "monitoring", element: withSuspense(<MonitoringPage />) },
          { path: "reports", element: withSuspense(<ReportsPage />) },
          { path: "users", element: withSuspense(<UsersRolesPage />) },
          { path: "notifications", element: withSuspense(<NotificationsPage />) },
          { path: "audit", element: withSuspense(<AuditPage />) },
          { path: "settings", element: withSuspense(<OrganizationSettingsPage />) },
          { path: "developer", element: withSuspense(<DeveloperPage />) },
          { path: "ads", element: withSuspense(<AdsPage />) },
          { path: "security", element: withSuspense(<SecurityPage />) },
          { path: "platform", element: withSuspense(<PlatformOverviewPage />) },
          { path: "platform/tenants", element: withSuspense(<TenantsPage />) },
          { path: "platform/tenants/:tenantId", element: withSuspense(<TenantDetailPage />) },
          { path: "platform/plans", element: withSuspense(<PlansPage />) },
          { path: "platform/plan-requests", element: withSuspense(<PlanRequestsPage />) },
          { path: "platform/invoices", element: withSuspense(<InvoicesPage />) },
          { path: "*", element: <ExceptionPage status={404} /> },
        ],
      },
    ],
  },
]);
