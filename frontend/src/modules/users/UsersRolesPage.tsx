import { Tabs } from "antd";
import { useState } from "react";
import { PageHeader } from "../../components/ui/PageHeader";
import { MembersTab } from "./MembersTab";
import { RolesTab } from "./RolesTab";
import { UsersTab } from "./UsersTab";

/** SCR-04 Users + SCR-05 Roles & Permissions + tenant members as tabs. */
export function UsersRolesPage() {
  const [tab, setTab] = useState<"users" | "roles" | "members">("users");

  return (
    <div>
      <PageHeader
        title="Users & Roles"
        description="Manage who can sign in, what they can do, and organization membership."
      />
      <Tabs
        activeKey={tab}
        onChange={(key) => setTab(key as typeof tab)}
        items={[
          { key: "users", label: "Users", children: <UsersTab /> },
          { key: "roles", label: "Roles", children: <RolesTab /> },
          { key: "members", label: "Members", children: <MembersTab /> },
        ]}
      />
    </div>
  );
}
