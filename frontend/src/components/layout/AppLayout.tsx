import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { GlobalSearch } from "./GlobalSearch";
import { TenantSwitcher } from "./TenantSwitcher";

const NAV = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/content", label: "Content" },
  { to: "/design", label: "Design" },
  { to: "/playlists", label: "Playlists" },
  { to: "/campaigns", label: "Campaigns" },
  { to: "/approvals", label: "Approvals" },
  { to: "/schedules", label: "Schedules" },
  { to: "/deployments", label: "Publishing" },
  { to: "/devices", label: "Devices" },
  { to: "/locations", label: "Locations" },
  { to: "/releases", label: "Updates" },
  { to: "/monitoring", label: "Monitoring" },
  { to: "/reports", label: "Reports" },
  { to: "/users", label: "Users & Roles" },
  { to: "/notifications", label: "Notifications" },
  { to: "/audit", label: "Audit Logs" },
  { to: "/settings", label: "Settings" },
  { to: "/developer", label: "Developer" },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function onLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 border-r border-slate-200 bg-white">
        <div className="flex h-14 items-center border-b border-slate-200 px-4">
          <span className="text-sm font-semibold tracking-wide text-slate-800">
            Digital Signage Cloud
          </span>
        </div>
        <nav className="space-y-0.5 p-2" aria-label="Primary">
          {[...NAV, ...(user?.is_superuser ? [{ to: "/platform", label: "Platform" }] : [])].map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-slate-900 text-white"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center gap-4 border-b border-slate-200 bg-white px-6">
          <GlobalSearch />
          <div className="ml-auto flex items-center gap-3">
            <TenantSwitcher />
            <span className="text-sm text-slate-600">{user?.full_name}</span>
          </div>
          <button
            type="button"
            onClick={onLogout}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            Sign out
          </button>
        </header>
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
