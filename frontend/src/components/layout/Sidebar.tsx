import { SIDEBAR_BG } from "@/design-system";
import { useThemeMode } from "@/design-system";
import { AccountMenu } from "./AccountMenu";
import { MainNavigation } from "./MainNavigation";
import { SidebarLogo } from "./SidebarLogo";

/**
 * The sidebar's three-band flex column, shared verbatim by the desktop
 * Sider and the mobile Drawer: the logo and account bands are
 * `flex-shrink: 0`, and only the navigation between them scrolls
 * (`flex: 1; min-height: 0; overflow-y: auto`).
 */
export function Sidebar({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const { mode } = useThemeMode();
  return (
    <div className="flex h-full flex-col" style={{ background: SIDEBAR_BG[mode] }}>
      <SidebarLogo collapsed={collapsed} />
      <MainNavigation collapsed={collapsed} onNavigate={onNavigate} />
      <AccountMenu collapsed={collapsed} />
    </div>
  );
}
