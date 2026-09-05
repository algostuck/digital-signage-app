

import { Input, InputNumber, Typography } from "antd";


export function PropField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Typography.Text type="secondary" className="block text-xs font-medium uppercase">
        {label}
      </Typography.Text>
      <div className="mt-1">{children}</div>
    </div>
  );
}

export function PropInput({
  label,
  value,
  onChange,
  type = "text",
  disabled = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  disabled?: boolean;
}) {
  return (
    <PropField label={label}>
      <Input
        type={type}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
      />
    </PropField>
  );
}

export function PropNumber({
  label,
  value,
  onChange,
  disabled = false,
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  disabled?: boolean;
}) {
  return (
    <PropField label={label}>
      <InputNumber
        className="w-full"
        value={value}
        disabled={disabled}
        onChange={onChange}
        aria-label={label}
      />
    </PropField>
  );
}
