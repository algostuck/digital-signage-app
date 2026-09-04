import { Form, theme, type FormItemProps } from "antd";
import type { ReactNode } from "react";

/** A Form.Item whose label sits on the control's top border, the way the
 * reference design draws it. antd has no floating-label variant, so this
 * is the one hand-positioned element on the auth screens; the control
 * itself, validation and messaging are all antd's. */
export function FloatingField({
  label,
  htmlFor,
  children,
  ...itemProps
}: FormItemProps & { label: string; htmlFor: string; children: ReactNode }) {
  const { token } = theme.useToken();
  return (
    <div className="relative">
      <label
        htmlFor={htmlFor}
        className="absolute z-[1] px-1.5"
        style={{
          top: -8,
          left: 16,
          fontSize: 12,
          lineHeight: "16px",
          background: token.colorBgContainer,
          color: token.colorTextSecondary,
        }}
      >
        {label}
      </label>
      <Form.Item {...itemProps}>{children}</Form.Item>
    </div>
  );
}

/** Pill geometry shared by every auth input. */
export const PILL_INPUT = { borderRadius: 999, height: 48, paddingInline: 18 } as const;
