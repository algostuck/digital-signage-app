import { useState } from "react";
import { MembersTab } from "./MembersTab";
import { RolesTab } from "./RolesTab";
import { UsersTab } from "./UsersTab";

/** SCR-04 Users + SCR-05 Roles & Permissions + tenant members as tabs. */
export function UsersRolesPage() {
  const [tab, setTab] = useState<"users" | "roles" | "members">("users");

  return (
    <div>
      <h1 className="text-xl font-semibold text-slate-900">Users &amp; Roles</h1>
      <div className="mt-4 border-b border-slate-200" role="tablist">
        {(["users", "roles", "members"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize ${
              tab === t
                ? "border-slate-900 text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="mt-4">
        {tab === "users" ? <UsersTab /> : tab === "roles" ? <RolesTab /> : <MembersTab />}
      </div>
    </div>
  );
}
