import { Alert, Button, Form, Input, Typography } from "antd";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { AuthShell, useAuthButtonStyle } from "./AuthShell";
import { FloatingField, PILL_INPUT } from "./FloatingField";

/** SCR-01 Login / Authentication. */
export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const buttonStyle = useAuthButtonStyle();

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
    <AuthShell>
      {error && (
        <Alert type="error" message={error} showIcon className="mb-5" role="alert" />
      )}
      <Form
        name="login"
        layout="vertical"
        onFinish={onFinish}
        requiredMark={false}
        aria-label="Sign in"
        size="large"
      >
        <FloatingField
          label="E-mail"
          htmlFor="login_email"
          name="email"
          rules={[
            { required: true, message: "Enter your email address." },
            { type: "email", message: "Enter a valid email address." },
          ]}
        >
          {/* No placeholder: antd renders it at ~1.8:1, and the floating
              label already names the field. */}
          <Input autoFocus autoComplete="email" style={PILL_INPUT} />
        </FloatingField>
        <FloatingField
          label="Password"
          htmlFor="login_password"
          name="password"
          rules={[{ required: true, message: "Enter your password." }]}
        >
          <Input.Password autoComplete="current-password" style={PILL_INPUT} />
        </FloatingField>

        <Button
          type="primary"
          htmlType="submit"
          loading={submitting}
          shape="round"
          size="large"
          className="min-w-[132px]"
          style={{ ...buttonStyle, marginTop: 13 }}
        >
          Login
        </Button>
      </Form>

      <Typography.Paragraph className="!mb-0" style={{ marginTop: 34 }}>
        <Link to="/forgot-password">Forgot Password?</Link>
      </Typography.Paragraph>
    </AuthShell>
  );
}
