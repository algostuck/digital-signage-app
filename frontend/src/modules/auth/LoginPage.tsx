import { LockOutlined, MailOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Form, Input, Typography, theme } from "antd";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";

/** SCR-01 Login / Authentication. */
export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = theme.useToken();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  async function onFinish(values: { email: string; password: string }) {
    setError(null);
    setSubmitting(true);
    try {
      await login(values.email, values.password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? err.message
          : "Unable to sign in. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center px-4"
      style={{ background: token.colorBgLayout }}
    >
      <Card className="w-full max-w-sm shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-base font-bold text-white">
            DS
          </div>
          <div>
            <Typography.Title level={4} className="!mb-0">
              Digital Signage Cloud
            </Typography.Title>
            <Typography.Text type="secondary">Sign in to your organization</Typography.Text>
          </div>
        </div>
        {error && (
          <Alert type="error" message={error} showIcon className="mb-4" role="alert" />
        )}
        <Form layout="vertical" onFinish={onFinish} requiredMark={false} aria-label="Sign in">
          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: "Enter your email address." },
              { type: "email", message: "Enter a valid email address." },
            ]}
          >
            <Input
              autoFocus
              autoComplete="email"
              prefix={<MailOutlined className="text-slate-400" />}
              placeholder="you@company.com"
            />
          </Form.Item>
          <Form.Item
            name="password"
            label="Password"
            rules={[{ required: true, message: "Enter your password." }]}
          >
            <Input.Password
              autoComplete="current-password"
              prefix={<LockOutlined className="text-slate-400" />}
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={submitting} size="large">
            Sign in
          </Button>
        </Form>
      </Card>
    </div>
  );
}
