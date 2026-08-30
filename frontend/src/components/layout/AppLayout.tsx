import {
  AppstoreOutlined,
  AuditOutlined,
  BarChartOutlined,
  BellOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  CloudUploadOutlined,
  CodeOutlined,
  CrownOutlined,
  DashboardOutlined,
  DesktopOutlined,
  DollarOutlined,
  EnvironmentOutlined,
  FolderOutlined,
  LineChartOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  PlaySquareOutlined,
  RocketOutlined,
  SafetyOutlined,
  SettingOutlined,
  SyncOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Avatar, Button, Drawer, Dropdown, Grid, Layout, Menu, Space, Typography } from "antd";
import { useMemo, useState } from "react";
import { NavLink, Outlet, ScrollRestoration, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { GlobalSearch } from "./GlobalSearch";
import { TenantSwitcher } from "./TenantSwitcher";

const { Header, Sider, Content } = Layout;
const { useBreakpoint } = Grid;

interface NavLeaf {
  key: string;
  icon: React.ReactNode;
  label: string;
}

const NAV_GROUPS: { label: string; items: NavLeaf[] }[] = [
  {
    label: "Content",
    items: [
      { key: "/content", icon: <FolderOutlined />, label: "Content Library" },
      { key: "/design", icon: <AppstoreOutlined />, label: "Design" },
      { key: "/playlists", icon: <PlaySquareOutlined />, label: "Playlists" },
    ],
  },
  {
    label: "Campaigns",
    items: [
      { key: "/campaigns", icon: <RocketOutlined />, label: "Campaigns" },
      { key: "/approvals", icon: <CheckCircleOutlined />, label: "Approvals" },
      { key: "/schedules", icon: <CalendarOutlined />, label: "Schedules" },
      { key: "/deployments", icon: <CloudUploadOutlined />, label: "Publishing" },
    ],
  },
  {
    label: "Devices",
    items: [
      { key: "/devices", icon: <DesktopOutlined />, label: "All Devices" },
      { key: "/locations", icon: <EnvironmentOutlined />, label: "Locations" },
      { key: "/monitoring", icon: <LineChartOutlined />, label: "Monitoring" },
      { key: "/releases", icon: <SyncOutlined />, label: "Updates" },
    ],
  },
  {
    label: "Insights",
    items: [
      { key: "/reports", icon: <BarChartOutlined />, label: "Reports" },
      { key: "/ads", icon: <DollarOutlined />, label: "Advertising" },
    ],
  },
  {
    label: "Administration",
    items: [
      { key: "/users", icon: <TeamOutlined />, label: "Users & Roles" },
      { key: "/notifications", icon: <BellOutlined />, label: "Notifications" },
      { key: "/audit", icon: <AuditOutlined />, label: "Audit Logs" },
      { key: "/security", icon: <SafetyOutlined />, label: "Security" },
      { key: "/developer", icon: <CodeOutlined />, label: "Developer" },
      { key: "/settings", icon: <SettingOutlined />, label: "Settings" },
    ],
  },
];

function buildMenuItems(isSuperuser: boolean, collapsed: boolean) {
  const leaf = (item: NavLeaf) => ({
    key: item.key,
    icon: item.icon,
    label: <NavLink to={item.key}>{item.label}</NavLink>,
  });
  const items: any[] = [
    { key: "/dashboard", icon: <DashboardOutlined />, label: <NavLink to="/dashboard">Dashboard</NavLink> },
    // Group headings don't fit the 80px collapsed rail — flatten there.
    ...(collapsed
      ? NAV_GROUPS.flatMap((group) => group.items.map(leaf))
      : NAV_GROUPS.map((group) => ({
          key: group.label,
          type: "group" as const,
          label: group.label,
          children: group.items.map(leaf),
        }))),
  ];
  if (isSuperuser) {
    items.push({
      key: "/platform",
      icon: <CrownOutlined />,
      label: <NavLink to="/platform">Platform</NavLink>,
    });
  }
  return items;
}

function selectedKeyFor(pathname: string, isSuperuser: boolean): string[] {
  const flatKeys = [
    "/dashboard",
    ...NAV_GROUPS.flatMap((g) => g.items.map((i) => i.key)),
    ...(isSuperuser ? ["/platform"] : []),
  ];
  const matches = flatKeys.filter((k) => pathname === k || pathname.startsWith(`${k}/`));
  matches.sort((a, b) => b.length - a.length);
  return matches.length > 0 ? [matches[0]] : [];
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <div className="flex h-14 items-center gap-2 px-4">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-blue-600 text-sm font-bold text-white">
        DS
      </div>
      {!collapsed && (
        <Typography.Text strong className="!text-white truncate">
          Digital Signage Cloud
        </Typography.Text>
      )}
    </div>
  );
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isSuperuser = user?.is_superuser ?? false;
  const menuItems = useMemo(
    () => buildMenuItems(isSuperuser, !isMobile && collapsed),
    [isSuperuser, isMobile, collapsed],
  );
  const selectedKeys = useMemo(
    () => selectedKeyFor(location.pathname, isSuperuser),
    [location.pathname, isSuperuser],
  );

  async function onLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  const userMenu = {
    items: [
      { key: "signout", icon: <LogoutOutlined />, label: "Sign out", onClick: onLogout },
    ],
  };

  const nav = (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={selectedKeys}
      items={menuItems}
      className="!border-r-0"
      onClick={() => setDrawerOpen(false)}
    />
  );

  return (
    <Layout className="min-h-screen">
      {isMobile ? (
        <Drawer
          placement="left"
          closable={false}
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          size={240}
          styles={{ body: { padding: 0, background: "#0F172A" } }}
        >
          <Brand collapsed={false} />
          {nav}
        </Drawer>
      ) : (
        <Sider theme="dark" collapsible collapsed={collapsed} trigger={null} width={240}>
          <Brand collapsed={collapsed} />
          {nav}
        </Sider>
      )}
      <Layout>
        <Header className="!flex items-center gap-4 !bg-white !px-4 shadow-sm">
          <Button
            type="text"
            aria-label={isMobile ? "Open navigation" : collapsed ? "Expand navigation" : "Collapse navigation"}
            icon={
              isMobile ? (
                <MenuOutlined />
              ) : collapsed ? (
                <MenuUnfoldOutlined />
              ) : (
                <MenuFoldOutlined />
              )
            }
            onClick={() => (isMobile ? setDrawerOpen(true) : setCollapsed((c) => !c))}
          />
          {!isMobile && <GlobalSearch />}
          <div className="ml-auto flex items-center gap-3">
            <TenantSwitcher />
            <Dropdown menu={userMenu} placement="bottomRight" trigger={["click"]}>
              <Space className="cursor-pointer" role="button" tabIndex={0} aria-label="Account menu">
                <Avatar size="small" icon={<UserOutlined />} />
                {!isMobile && <Typography.Text>{user?.full_name}</Typography.Text>}
              </Space>
            </Dropdown>
          </div>
        </Header>
        {/* Width-capped and centered so ultra-wide monitors get balanced
            whitespace instead of endless line lengths (brief §56). */}
        <Content className="m-4 w-full max-w-[1600px] md:m-6 xl:mx-auto">
          <ScrollRestoration />
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
