import {
  AppstoreOutlined,
  AuditOutlined,
  BarChartOutlined,
  BellOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  CloudUploadOutlined,
  CodeOutlined,
  ControlOutlined,
  CrownOutlined,
  DashboardOutlined,
  DesktopOutlined,
  DollarOutlined,
  EnvironmentOutlined,
  FileImageOutlined,
  FolderOutlined,
  LineChartOutlined,
  PlaySquareOutlined,
  RocketOutlined,
  SafetyOutlined,
  SettingOutlined,
  SyncOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import type { MenuProps } from "antd";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

/**
 * The single authoritative definition of the product's primary
 * navigation. Nothing else in the app declares menu structure — the
 * shell filters this by RBAC and renders it through antd's Menu.
 *
 * `permission` lists are ANY-OF and mirror the real server-side gates
 * (see docs/SIDEBAR_UX_AUDIT.md §3), so a visible item is always a
 * reachable page. Submenu parents carry no permission of their own:
 * they disappear when every child is filtered away.
 */
export interface NavNode {
  /** Stable menu key — the route path for destinations. */
  key: string;
  label: string;
  icon?: ReactNode;
  /** Destination route. Absent on pure submenu parents. */
  path?: string;
  /** Any-of permission codes required to see this item. */
  permission?: string[];
  superuserOnly?: boolean;
  children?: NavNode[];
}

export const NAVIGATION: NavNode[] = [
  {
    key: "/dashboard",
    label: "Dashboard",
    icon: <DashboardOutlined />,
    path: "/dashboard",
    // Never filtered: it is the index redirect target and degrades to an
    // in-page error state if monitoring data is unavailable.
  },
  {
    key: "content",
    label: "Content",
    icon: <FolderOutlined />,
    children: [
      {
        key: "/content",
        label: "Media Library",
        path: "/content",
        icon: <FileImageOutlined />,
        permission: ["content.view"],
      },
      {
        key: "/design",
        label: "Design Studio",
        path: "/design",
        icon: <AppstoreOutlined />,
        permission: ["layouts.view"],
      },
      {
        key: "/playlists",
        label: "Playlists",
        path: "/playlists",
        icon: <PlaySquareOutlined />,
        permission: ["playlists.view"],
      },
    ],
  },
  {
    key: "campaigns",
    label: "Campaigns",
    icon: <RocketOutlined />,
    children: [
      {
        key: "/campaigns",
        label: "Campaigns",
        path: "/campaigns",
        icon: <RocketOutlined />,
        permission: ["campaigns.view"],
      },
      {
        key: "/approvals",
        label: "Approvals",
        path: "/approvals",
        icon: <CheckCircleOutlined />,
        permission: ["campaigns.approve", "layouts.manage", "settings.manage"],
      },
      {
        key: "/schedules",
        label: "Schedule",
        path: "/schedules",
        icon: <CalendarOutlined />,
        permission: ["schedules.view"],
      },
      {
        key: "/deployments",
        label: "Publishing",
        path: "/deployments",
        icon: <CloudUploadOutlined />,
        permission: ["deployments.view"],
      },
    ],
  },
  {
    key: "devices",
    label: "Devices",
    icon: <DesktopOutlined />,
    children: [
      {
        key: "/devices",
        label: "All Devices",
        path: "/devices",
        icon: <DesktopOutlined />,
        permission: ["devices.view"],
      },
      {
        key: "/monitoring",
        label: "Monitoring",
        path: "/monitoring",
        icon: <LineChartOutlined />,
        permission: ["monitoring.view"],
      },
      {
        key: "/releases",
        label: "Player Updates",
        path: "/releases",
        icon: <SyncOutlined />,
        permission: ["releases.manage"],
      },
    ],
  },
  {
    key: "/locations",
    label: "Locations",
    icon: <EnvironmentOutlined />,
    path: "/locations",
    permission: ["locations.view"],
  },
  {
    key: "reports",
    label: "Reports",
    icon: <BarChartOutlined />,
    children: [
      {
        key: "/reports",
        label: "Reports & Analytics",
        path: "/reports",
        icon: <BarChartOutlined />,
        permission: ["reports.view"],
      },
      {
        key: "/ads",
        label: "Advertising",
        path: "/ads",
        icon: <DollarOutlined />,
        permission: ["ads.view"],
      },
    ],
  },
  {
    key: "administration",
    label: "Administration",
    icon: <ControlOutlined />,
    children: [
      {
        key: "/users",
        label: "Users & Roles",
        path: "/users",
        icon: <TeamOutlined />,
        permission: ["users.view"],
      },
      {
        key: "/notifications",
        label: "Notifications",
        path: "/notifications",
        icon: <BellOutlined />,
        permission: ["notifications.view"],
      },
      {
        key: "/audit",
        label: "Audit Logs",
        path: "/audit",
        icon: <AuditOutlined />,
        permission: ["audit.view"],
      },
      {
        key: "/security",
        label: "Security",
        path: "/security",
        icon: <SafetyOutlined />,
        permission: ["settings.manage"],
      },
      {
        key: "/developer",
        label: "Developer",
        path: "/developer",
        icon: <CodeOutlined />,
        permission: ["api_keys.manage"],
      },
    ],
  },
  {
    key: "/settings",
    label: "Settings",
    icon: <SettingOutlined />,
    path: "/settings",
    permission: ["organization.view"],
  },
  {
    // Super Admin only. Each area is its own page: the console used to be
    // one long screen mixing tenants, plans, requests and invoices.
    key: "platform-console",
    label: "Platform Console",
    icon: <CrownOutlined />,
    superuserOnly: true,
    children: [
      {
        key: "/platform",
        label: "Overview",
        path: "/platform",
        icon: <DashboardOutlined />,
        superuserOnly: true,
      },
      {
        key: "/platform/tenants",
        label: "Tenants",
        path: "/platform/tenants",
        icon: <TeamOutlined />,
        superuserOnly: true,
      },
      {
        key: "/platform/plans",
        label: "Plans",
        path: "/platform/plans",
        icon: <AppstoreOutlined />,
        superuserOnly: true,
      },
      {
        key: "/platform/plan-requests",
        label: "Plan requests",
        path: "/platform/plan-requests",
        icon: <AuditOutlined />,
        superuserOnly: true,
      },
      {
        key: "/platform/invoices",
        label: "Invoices",
        path: "/platform/invoices",
        icon: <DollarOutlined />,
        superuserOnly: true,
      },
    ],
  },
];

export interface NavAccess {
  hasPermission: (code: string) => boolean;
  isSuperuser: boolean;
}

function isVisible(node: NavNode, access: NavAccess): boolean {
  if (node.superuserOnly && !access.isSuperuser) return false;
  if (node.permission && !node.permission.some(access.hasPermission)) return false;
  return true;
}

/** RBAC filter. Submenus with no surviving children are dropped. */
export function filterNavigation(nodes: NavNode[], access: NavAccess): NavNode[] {
  const out: NavNode[] = [];
  for (const node of nodes) {
    if (!isVisible(node, access)) continue;
    if (node.children) {
      const children = filterNavigation(node.children, access);
      if (children.length === 0) continue;
      out.push({ ...node, children });
    } else {
      out.push(node);
    }
  }
  return out;
}

function leafItem(node: NavNode, showIcon: boolean) {
  return {
    key: node.key,
    icon: showIcon ? node.icon : undefined,
    label: node.path ? <Link to={node.path}>{node.label}</Link> : node.label,
  };
}

/**
 * antd Menu items. Destinations render a real `<Link>` so middle-click
 * and open-in-new-tab keep working; the shell also wires Menu.onClick so
 * the whole row (not just the anchor) is clickable.
 *
 * `flatten` is used for the collapsed 80px rail: every destination is
 * lifted to the top level with its own icon, so the rail stays one click
 * from anywhere. Expanded, children are icon-free so the parent icon
 * carries module identity and the hierarchy reads cleanly.
 */
export function toMenuItems(nodes: NavNode[], flatten = false): MenuProps["items"] {
  if (flatten) {
    return nodes.flatMap((node) =>
      node.children ? node.children.map((child) => leafItem(child, true)) : [leafItem(node, true)],
    );
  }
  return nodes.map((node) =>
    node.children
      ? {
          key: node.key,
          icon: node.icon,
          label: node.label,
          children: node.children.map((child) => leafItem(child, false)),
        }
      : leafItem(node, true),
  );
}

/** Flat key → path index for the shell's row-click handler. */
export function pathIndex(nodes: NavNode[], into: Map<string, string> = new Map()) {
  for (const node of nodes) {
    if (node.path) into.set(node.key, node.path);
    if (node.children) pathIndex(node.children, into);
  }
  return into;
}

/**
 * Route → menu state. Uses longest-prefix matching so nested routes
 * (`/design/:layoutId`, `/playlists/:id`) select their parent entry, and
 * returns the owning submenu so deep links and refreshes restore the
 * expanded section.
 */
export function matchNavigation(
  nodes: NavNode[],
  pathname: string,
): { selectedKeys: string[]; openKeys: string[] } {
  let best: { node: NavNode; parent?: NavNode } | null = null;
  const walk = (list: NavNode[], parent?: NavNode) => {
    for (const node of list) {
      if (node.path && (pathname === node.path || pathname.startsWith(`${node.path}/`))) {
        if (!best || node.path.length > (best.node.path?.length ?? 0)) best = { node, parent };
      }
      if (node.children) walk(node.children, node);
    }
  };
  walk(nodes);
  if (!best) return { selectedKeys: [], openKeys: [] };
  const match = best as { node: NavNode; parent?: NavNode };
  return {
    selectedKeys: [match.node.key],
    openKeys: match.parent ? [match.parent.key] : [],
  };
}
