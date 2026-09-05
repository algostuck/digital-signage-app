import { Alert, Button, Form, Input, Result, Space, Typography } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../lib/api";
import { AuthShell } from "./AuthShell";

type Step = "request" | "confirm" | "done";

/** Password reset. The backend always answers a request with success (no
 * account enumeration) and e-mails a token when the account exists, so the
 * second step asks for that token plus the new password. */
export function ForgotPasswordPage() {
  const [step, setStep] = useState<Step>("request");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function request(values: { email: string }) {
    setError(null);
    setBusy(true);
    try {
      await api.post("/auth/password-reset/request", { email: values.email });
      setStep("confirm");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? "Too many attempts. Wait a minute and try again."
          : "Could not request a reset. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirm(values: { token: string; password: string }) {
    setError(null);
    setBusy(true);
    try {
      await api.post("/auth/password-reset/confirm", {
        token: values.token.trim(),
        new_password: values.password,
      });
      setStep("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reset the password. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (step === "done") {
    return (
      <AuthShell>
        <Result
          status="success"
          title="Password updated"
          subTitle="Sign in with your new password."
          extra={
            <Link to="/login">
              <Button type="primary" size="large">
                Back to sign in
              </Button>
            </Link>
          }
        />
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={step === "request" ? "Reset your password" : "Enter your reset token"}
      description={
        step === "request"
          ? "We'll e-mail a reset token if an account exists for this address."
          : "Paste the token from the e-mail and choose a new password (10+ characters)."
      }
    >
      {error && <Alert type="error" title={error} showIcon style={{ marginBottom: 20 }} role="alert" />}
      {step === "confirm" && !error && (
        <Alert type="info" showIcon style={{ marginBottom: 20 }} title="If that address has an account, a token is on its way." />
      )}

      {step === "request" ? (
        <Form name="reset" layout="vertical" onFinish={request} size="large">
          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: "Enter your email address." },
              { type: "email", message: "Enter a valid email address." },
            ]}
          >
            <Input autoFocus autoComplete="email" />
          </Form.Item>
          <Space wrap>
            <Button type="primary" htmlType="submit" loading={busy} size="large">
              Send reset token
            </Button>
            <Button type="link" onClick={() => setStep("confirm")}>
              I already have a token
            </Button>
          </Space>
        </Form>
      ) : (
        <Form name="confirm" layout="vertical" onFinish={confirm} size="large">
          <Form.Item name="token" label="Reset token" rules={[{ required: true, message: "Paste the token from the e-mail." }]}>
            <Input autoFocus autoComplete="one-time-code" />
          </Form.Item>
          <Form.Item
            name="password"
            label="New password"
            rules={[
              { required: true, message: "Choose a new password." },
              { min: 10, message: "Use at least 10 characters." },
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={busy} size="large">
            Set new password
          </Button>
        </Form>
      )}

      <Typography.Paragraph style={{ marginTop: 24, marginBottom: 0 }}>
        <Link to="/login">Back to sign in</Link>
      </Typography.Paragraph>
    </AuthShell>
  );
}
