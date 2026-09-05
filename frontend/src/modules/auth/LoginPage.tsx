import { LockOutlined, MailOutlined } from "@ant-design/icons";
import { Alert, Button, Form, Input, Typography } from "antd";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { AuthShell } from "./AuthShell";

/** SCR-01 Login / Authentication — a standard vertical antd Form
 * (docs/design-system/DESIGN_SYSTEM_USAGE.md §2) inside the brand shell. */
export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
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
    <AuthShell title="Sign in" description="Use your organisation account to continue.">
      {error && <Alert type="error" title={error} showIcon style={{ marginBottom: 20 }} role="alert" />}
      <Form name="login" layout="vertical" onFinish={onFinish} aria-label="Sign in" size="large">
        <Form.Item
          name="email"
          label="Email"
          rules={[
            { required: true, message: "Enter your email address." },
            { type: "email", message: "Enter a valid email address." },
          ]}
        >
          <Input autoFocus autoComplete="email" prefix={<MailOutlined aria-hidden />} />
        </Form.Item>
        <Form.Item name="password" label="Password" rules={[{ required: true, message: "Enter your password." }]}>
          <Input.Password autoComplete="current-password" prefix={<LockOutlined aria-hidden />} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={submitting} size="large" block style={{ marginTop: 8 }}>
          Sign in
        </Button>
      </Form>
      <Typography.Paragraph style={{ marginTop: 24, marginBottom: 0 }}>
        <Link to="/forgot-password">Forgot your password?</Link>
      </Typography.Paragraph>
    </AuthShell>
  );
}
