import { BellOutlined, MoonOutlined, SunOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Badge, Button, Tooltip } from "antd";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useThemeMode } from "../../theme/ThemeProvider";

interface Summary {
  notifications_unread: number;
}

/** Right-hand header cluster: unread notifications and the theme switch. */
export function HeaderActions() {
  const { mode, toggle } = useThemeMode();
  const { hasPermission } = useAuth();
  const navigate = useNavigate();

  const canSeeNotifications = hasPermission("notifications.view");
  // The monitoring summary already carries an authoritative unread count
  // and is shared (same query key) with the dashboard, so the badge costs
  // no extra request while the user is there.
  const summary = useQuery({
    queryKey: ["monitoring-summary"],
    queryFn: () => api.get<Summary>("/monitoring/summary"),
    enabled: canSeeNotifications && hasPermission("monitoring.view"),
    refetchInterval: 60_000,
  });
  const unread = summary.data?.data?.notifications_unread ?? 0;

  return (
    <>
      {canSeeNotifications && (
        <Tooltip title={unread > 0 ? `${unread} unread notifications` : "Notifications"}>
          <Badge count={unread} size="small" overflowCount={99} offset={[-2, 2]}>
            <Button
              type="text"
              shape="circle"
              icon={<BellOutlined />}
              aria-label={
                unread > 0 ? `Notifications, ${unread} unread` : "Notifications"
              }
              onClick={() => navigate("/notifications")}
            />
          </Badge>
        </Tooltip>
      )}
      <Tooltip title={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}>
        <Button
          type="text"
          shape="circle"
          icon={mode === "dark" ? <SunOutlined /> : <MoonOutlined />}
          aria-label={mode === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          aria-pressed={mode === "dark"}
          onClick={toggle}
        />
      </Tooltip>
    </>
  );
}
