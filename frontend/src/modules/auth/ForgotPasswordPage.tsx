import { Alert, Button, Form, Input, Result, Space, Typography } from "antd";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../../lib/api";
import { AuthShell, useAuthButtonStyle } from "./AuthShell";
import { FloatingField, PILL_INPUT } from "./FloatingField";

type Step = "request" | "confirm" | "done";

/** Password reset. The backend always answers a request with success (no
 * account enumeration) and e-mails a token when the account exists, so the
 * second step asks for that token plus the new password. */
export function ForgotPasswordPage() {
  const [step, setStep] = useState<Step>("request");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const SUBMIT_STYLE = useAuthButtonStyle();

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
      setError(
        err instanceof ApiError ? err.message : "Could not reset the password. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell>
      {step === "done" ? (
        <Result
          status="success"
          title="Password updated"
          subTitle="Sign in with your new password."
          extra={
            <Link to="/login">
              <Button type="primary" shape="round" size="large" style={SUBMIT_STYLE}>
                Back to login
              </Button>
            </Link>
          }
        />
      ) : (
        <>
          <Typography.Title level={4} className="!mb-1">
            {step === "request" ? "Reset your password" : "Enter your reset token"}
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 21 }}>
            {step === "request"
              ? "We'll e-mail a reset token if an account exists for this address."
              : "Paste the token from the e-mail and choose a new password (10+ characters)."}
          </Typography.Paragraph>

          {error && (
            <Alert type="error" message={error} showIcon className="mb-5" role="alert" />
          )}
          {step === "confirm" && !error && (
            <Alert
              type="info"
              showIcon
              className="mb-5"
              message="If that address has an account, a token is on its way."
            />
          )}

          {step === "request" ? (
            <Form name="reset" layout="vertical" onFinish={request} requiredMark={false} size="large">
              <FloatingField
                label="E-mail"
                htmlFor="reset_email"
                name="email"
                rules={[
                  { required: true, message: "Enter your email address." },
                  { type: "email", message: "Enter a valid email address." },
                ]}
              >
                <Input autoFocus autoComplete="email" style={PILL_INPUT} />
              </FloatingField>
              <Space wrap>
                <Button type="primary" htmlType="submit" loading={busy} shape="round" size="large" style={SUBMIT_STYLE}>
                  Send reset token
                </Button>
                <Button type="link" onClick={() => setStep("confirm")}>
                  I already have a token
                </Button>
              </Space>
            </Form>
          ) : (
            <Form name="confirm" layout="vertical" onFinish={confirm} requiredMark={false} size="large">
              <FloatingField
                label="Reset token"
                htmlFor="confirm_token"
                name="token"
                rules={[{ required: true, message: "Paste the token from the e-mail." }]}
              >
                <Input autoFocus autoComplete="one-time-code" style={PILL_INPUT} />
              </FloatingField>
              <FloatingField
                label="New password"
                htmlFor="confirm_password"
                name="password"
                rules={[
                  { required: true, message: "Choose a new password." },
                  { min: 10, message: "Use at least 10 characters." },
                ]}
              >
                <Input.Password autoComplete="new-password" style={PILL_INPUT} />
              </FloatingField>
              <Button type="primary" htmlType="submit" loading={busy} shape="round" size="large" style={SUBMIT_STYLE}>
                Set new password
              </Button>
            </Form>
          )}

          <Typography.Paragraph className="!mb-0" style={{ marginTop: 34 }}>
            <Link to="/login">Back to login</Link>
          </Typography.Paragraph>
        </>
      )}
    </AuthShell>
  );
}
