import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { DashboardPage } from "../modules/dashboard/DashboardPage";
import { LoginPage } from "../modules/auth/LoginPage";
import { ApprovalsPage } from "../modules/approvals/ApprovalsPage";
import { CampaignsPage } from "../modules/campaigns/CampaignsPage";
import { DeploymentsPage } from "../modules/campaigns/DeploymentsPage";
import { SchedulesPage } from "../modules/campaigns/SchedulesPage";
import { ContentPage } from "../modules/content/ContentPage";
import { DesignerPage } from "../modules/design/DesignerPage";
import { LayoutsPage } from "../modules/design/LayoutsPage";
import { DevicesPage } from "../modules/devices/DevicesPage";
import { LocationsPage } from "../modules/locations/LocationsPage";
import { AuditPage } from "../modules/ops/AuditPage";
import { NotificationsPage } from "../modules/ops/NotificationsPage";
import { ReportsPage } from "../modules/ops/ReportsPage";
import { PlaylistEditorPage } from "../modules/playlists/PlaylistEditorPage";
import { PlaylistsPage } from "../modules/playlists/PlaylistsPage";
import { MonitoringPage } from "../modules/monitoring/MonitoringPage";
import { ReleasesPage } from "../modules/releases/ReleasesPage";
import { AdsPage } from "../modules/ads/AdsPage";
import { DeveloperPage } from "../modules/developer/DeveloperPage";
import { OrganizationSettingsPage } from "../modules/organization/OrganizationSettingsPage";
import { PlatformPage } from "../modules/platform/PlatformPage";
import { UsersRolesPage } from "../modules/users/UsersRolesPage";
import { ProtectedRoute } from "./ProtectedRoute";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: "/",
        element: <AppLayout />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },
          { path: "dashboard", element: <DashboardPage /> },
          { path: "content", element: <ContentPage /> },
          { path: "design", element: <LayoutsPage /> },
          { path: "design/:layoutId", element: <DesignerPage /> },
          { path: "playlists", element: <PlaylistsPage /> },
          { path: "playlists/:playlistId", element: <PlaylistEditorPage /> },
          { path: "campaigns", element: <CampaignsPage /> },
          { path: "approvals", element: <ApprovalsPage /> },
          { path: "schedules", element: <SchedulesPage /> },
          { path: "deployments", element: <DeploymentsPage /> },
          { path: "devices", element: <DevicesPage /> },
          { path: "locations", element: <LocationsPage /> },
          { path: "releases", element: <ReleasesPage /> },
          { path: "monitoring", element: <MonitoringPage /> },
          { path: "reports", element: <ReportsPage /> },
          { path: "users", element: <UsersRolesPage /> },
          { path: "notifications", element: <NotificationsPage /> },
          { path: "audit", element: <AuditPage /> },
          { path: "settings", element: <OrganizationSettingsPage /> },
          { path: "developer", element: <DeveloperPage /> },
          { path: "ads", element: <AdsPage /> },
          { path: "platform", element: <PlatformPage /> },
        ],
      },
    ],
  },
]);
