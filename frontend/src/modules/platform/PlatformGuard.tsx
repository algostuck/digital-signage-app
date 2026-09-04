import { Result } from "antd";
import type { ReactNode } from "react";
import { useAuth } from "../../lib/auth";

/** Every console page renders through this. The navigation already hides
 * the section from non-superusers; this covers deep links and bookmarks. */
export function PlatformGuard({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (!user?.is_superuser) {
    return (
      <Result
        status="403"
        title="Platform Console unavailable"
        subTitle="Platform administrator access is required for this area."
      />
    );
  }
  return <>{children}</>;
}

export const PLATFORM_CRUMB = { label: "Platform Console", to: "/platform" };
