import { Menu, Typography } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  filterNavigation,
  matchNavigation,
  NAVIGATION,
  pathIndex,
  toMenuItems,
} from "../../config/navigation";
import { useAuth } from "../../lib/auth";
import { useThemeMode } from "../../theme/ThemeProvider";

interface Props {
  collapsed: boolean;
  /** Called after a destination is chosen — the mobile drawer closes on it. */
  onNavigate?: () => void;
}

/**
 * The scrolling middle band of the sidebar. antd's Menu supplies the ARIA
 * roles, roving tabindex and arrow-key behavior; this component only owns
 * the RBAC filter and the route↔menu-state mapping.
 */
export function MainNavigation({ collapsed, onNavigate }: Props) {
  const { hasPermission, user } = useAuth();
  const { mode } = useThemeMode();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const nodes = useMemo(
    () => filterNavigation(NAVIGATION, { hasPermission, isSuperuser: user?.is_superuser ?? false }),
    [hasPermission, user?.is_superuser],
  );
  // Collapsed, the rail flattens to destinations: antd 6 does not mount
  // popup portals for inline-collapsed submenus (and forcing them renders
  // the popups in-flow, stretching the rail to full width), so grouping
  // would leave sections unopenable. See docs/SIDEBAR_UX_AUDIT.md §7.
  const items = useMemo(() => toMenuItems(nodes, collapsed), [nodes, collapsed]);
  const paths = useMemo(() => pathIndex(nodes), [nodes]);
  const { selectedKeys, openKeys: routeOpenKeys } = useMemo(
    () => matchNavigation(nodes, pathname),
    [nodes, pathname],
  );

  // Seeded from the route so deep links and refreshes restore the right
  // section; the union on navigation keeps sections the user opened
  // themselves from snapping shut as they move around.
  const [openKeys, setOpenKeys] = useState<string[]>(routeOpenKeys);
  useEffect(() => {
    setOpenKeys((prev) => Array.from(new Set([...prev, ...routeOpenKeys])));
  }, [routeOpenKeys]);

  return (
    <nav aria-label="Main navigation" className="sidebar-scroll min-h-0 flex-1 overflow-y-auto py-4">
      {!collapsed && (
        <Typography.Text
          type="secondary"
          className="block px-4 pb-2 !text-xs font-semibold uppercase tracking-wider"
        >
          Main navigation
        </Typography.Text>
      )}
      <Menu
        theme={mode}
        mode="inline"
        items={items}
        // Expanded: we control which sections are open. Collapsed: antd
        // drives its own popup state through the same prop, so it must be
        // left uncontrolled — remounting on the switch stops the previous
        // mode's state leaking across (which renders submenus inline
        // inside the 80px rail).
        key={collapsed ? "rail" : "full"}
        selectedKeys={selectedKeys}
        {...(collapsed ? {} : { openKeys, onOpenChange: setOpenKeys })}
        inlineIndent={24}
        className="!border-e-0 !bg-transparent"
        onClick={({ key }) => {
          const path = paths.get(key);
          // The <Link> in the label handles anchor clicks; this makes the
          // rest of the row clickable too.
          if (path && path !== pathname) navigate(path);
          onNavigate?.();
        }}
      />
    </nav>
  );
}
