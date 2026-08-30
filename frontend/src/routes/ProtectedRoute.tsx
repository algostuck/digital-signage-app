import { Flex, Spin } from "antd";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";

export function ProtectedRoute() {
  const { user, initializing } = useAuth();
  const location = useLocation();

  if (initializing) {
    return (
      <Flex align="center" justify="center" className="min-h-screen">
        <Spin size="large" description="Restoring session…">
          <div className="p-12" aria-hidden />
        </Spin>
      </Flex>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
