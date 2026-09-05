import { MenuFoldOutlined, MenuOutlined, MenuUnfoldOutlined } from "@ant-design/icons";
import { Button, Drawer, Flex, Grid, Layout, theme } from "antd";
import { useEffect, useMemo, useState } from "react";
import { Outlet, ScrollRestoration } from "react-router-dom";
import { BreadcrumbProvider, SHELL, SIDEBAR_BG, useThemeMode } from "@/design-system";
import { breadcrumbsFor, filterNavigation, NAVIGATION } from "../../config/navigation";
import { useAuth } from "../../lib/auth";
import { GlobalSearch } from "./GlobalSearch";
import { HeaderActions } from "./HeaderActions";
import { Sidebar } from "./Sidebar";
import { TenantSwitcher } from "./TenantSwitcher";

const { Header, Sider, Content } = Layout;
const { useBreakpoint } = Grid;

/**
 * Application shell (docs/design-system/COMPONENT_CATALOGUE.md): antd
 * Layout with a sticky Sider ≥ md (collapsible to the 80px rail), a
 * Drawer below md, a 55px header and a centred content container. It also
 * provides the breadcrumb resolver every PageHeader derives its trail from.
 */
export function AppLayout() {
  const { token } = theme.useToken();
  const { mode } = useThemeMode();
  const { hasPermission, user } = useAuth();
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const isTablet = Boolean(screens.md) && !screens.lg;
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Tablets start on the icon rail so the content keeps a usable width;
  // desktops start expanded. The user's own toggle wins from then on.
  useEffect(() => {
    if (!isMobile) setCollapsed(isTablet);
  }, [isMobile, isTablet]);

  const resolveBreadcrumbs = useMemo(() => {
    const nodes = filterNavigation(NAVIGATION, {
      hasPermission,
      isSuperuser: user?.is_superuser ?? false,
    });
    return (pathname: string) => breadcrumbsFor(nodes, pathname);
  }, [hasPermission, user?.is_superuser]);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {isMobile ? (
        <Drawer
          placement="left"
          closable={false}
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          size={SHELL.siderWidth}
          styles={{ body: { padding: 0, background: SIDEBAR_BG[mode] } }}
        >
          <Sidebar onNavigate={() => setDrawerOpen(false)} />
        </Drawer>
      ) : (
        <Sider
          theme={mode}
          width={SHELL.siderWidth}
          collapsedWidth={SHELL.siderCollapsedWidth}
          collapsible
          collapsed={collapsed}
          trigger={null}
          // Pinned to the viewport so the logo and account bands stay put
          // no matter how long the page is; only the nav band scrolls.
          style={{
            height: "100vh",
            position: "sticky",
            top: 0,
            insetInlineStart: 0,
            borderInlineEnd: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          <Sidebar collapsed={collapsed} />
        </Sider>
      )}

      <Layout>
        <Header
          style={{
            display: "flex",
            alignItems: "center",
            gap: token.marginSM,
            paddingInline: token.padding,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          <Button
            type="text"
            aria-label={
              isMobile ? "Open navigation" : collapsed ? "Expand navigation" : "Collapse navigation"
            }
            aria-expanded={isMobile ? drawerOpen : !collapsed}
            icon={isMobile ? <MenuOutlined /> : collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => (isMobile ? setDrawerOpen(true) : setCollapsed((c) => !c))}
          />
          {!isMobile && <GlobalSearch />}
          <Flex align="center" gap={token.marginXS} style={{ marginInlineStart: "auto" }}>
            <TenantSwitcher />
            <HeaderActions />
          </Flex>
        </Header>
        {/* Centered container, applied once for every screen: 24px page
            gutters (16px below md) on the Content, and an inner wrapper
            with auto margins whose max-width is 88cqw of the Content,
            floored at 1024px and capped at 1440px (SHELL.contentMaxWidth). Container units, not viewport
            units, so it stays correct whether the sidebar is expanded,
            collapsed or a drawer. */}
        <Content
          style={{
            padding: isMobile ? token.padding : token.paddingLG,
            containerType: "inline-size",
          }}
        >
          <div style={{ marginInline: "auto", width: "100%", maxWidth: SHELL.contentMaxWidth }}>
            <ScrollRestoration />
            <BreadcrumbProvider resolve={resolveBreadcrumbs}>
              <Outlet />
            </BreadcrumbProvider>
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
