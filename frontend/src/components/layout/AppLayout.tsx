import { MenuFoldOutlined, MenuOutlined, MenuUnfoldOutlined } from "@ant-design/icons";
import { Button, Drawer, Grid, Layout, theme } from "antd";
import { useEffect, useState } from "react";
import { Outlet, ScrollRestoration } from "react-router-dom";
import { SIDEBAR_BG } from "../../theme/tokens";
import { useThemeMode } from "../../theme/ThemeProvider";
import { GlobalSearch } from "./GlobalSearch";
import { HeaderActions } from "./HeaderActions";
import { Sidebar } from "./Sidebar";
import { TenantSwitcher } from "./TenantSwitcher";

const { Header, Sider, Content } = Layout;
const { useBreakpoint } = Grid;

const SIDER_WIDTH = 260;

export function AppLayout() {
  const { token } = theme.useToken();
  const { mode } = useThemeMode();
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

  return (
    <Layout className="min-h-screen">
      {isMobile ? (
        <Drawer
          placement="left"
          closable={false}
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          size={SIDER_WIDTH}
          styles={{ body: { padding: 0, background: SIDEBAR_BG[mode] } }}
        >
          <Sidebar onNavigate={() => setDrawerOpen(false)} />
        </Drawer>
      ) : (
        <Sider
          theme={mode}
          width={SIDER_WIDTH}
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
          className="!flex items-center gap-3 !px-4"
          style={{ borderBottom: `1px solid ${token.colorBorderSecondary}` }}
        >
          <Button
            type="text"
            aria-label={
              isMobile
                ? "Open navigation"
                : collapsed
                  ? "Expand navigation"
                  : "Collapse navigation"
            }
            aria-expanded={isMobile ? drawerOpen : !collapsed}
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
          <div className="ml-auto flex items-center gap-2">
            <TenantSwitcher />
            <HeaderActions />
          </div>
        </Header>
        {/* Centered container, applied once for every screen: 24px page
            gutters (16px below md) on the Content, and an inner wrapper
            with auto margins whose max-width follows the golden ratio of
            the space beside the sidebar — 61.8cqw of the Content, floored
            at 1024px (Tailwind's 5xl) and capped at 1440px. Container
            units, not viewport units, so it stays correct whether the
            sidebar is expanded, collapsed or a drawer. */}
        <Content className="p-4 md:p-6" style={{ containerType: "inline-size" }}>
          <div className="mx-auto w-full" style={{ maxWidth: "clamp(1024px, 61.8cqw, 1440px)" }}>
            <ScrollRestoration />
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
