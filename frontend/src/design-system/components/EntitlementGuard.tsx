import { LockOutlined } from "@ant-design/icons";
import { Button } from "antd";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useEntitlements } from "../../lib/entitlements";
import { ExceptionPage } from "./ExceptionPage";

interface EntitlementGuardProps {
  /** Entitlement key, e.g. "sso", "experiments", "video_wall". */
  feature: string;
  /** Human name shown in the locked state. */
  featureName: string;
  children: ReactNode;
}

/** Renders children when the tenant's plan includes the feature;
 * otherwise a consistent "upgrade to unlock" state (audit finding #5).
 * UI affordance only — the server still enforces entitlements. */
export function EntitlementGuard({ feature, featureName, children }: EntitlementGuardProps) {
  const { hasFeature, entitlements } = useEntitlements();
  if (hasFeature(feature)) return <>{children}</>;
  return (
    <ExceptionPage
      status={403}
      icon={<LockOutlined />}
      title={`${featureName} is not included in your plan`}
      description={
        entitlements?.plan_name
          ? `Your current plan is ${entitlements.plan_name}. Upgrade to unlock this feature.`
          : "Upgrade your plan to unlock this feature."
      }
      actions={
        <Link to="/settings">
          <Button type="primary">View plans</Button>
        </Link>
      }
    />
  );
}
