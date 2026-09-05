import { Popconfirm } from "antd";
import { cloneElement, isValidElement, type MouseEvent, type ReactElement, type ReactNode } from "react";
import { useFeedback } from "../utilities/feedback";

interface ConfirmActionProps {
  /** What is about to happen, as a question: "Delete Kolkata Store 3?" */
  title: ReactNode;
  /** The consequence, one sentence: "Its 4 screens keep playing until republished." */
  consequence?: ReactNode;
  /** Verb on the confirm button; defaults by severity (Delete / Confirm). */
  okText?: string;
  /** `low` = inline Popconfirm (reversible or contained); `high` = blocking
   * modal (irreversible, wide blast radius). */
  severity?: "low" | "high";
  danger?: boolean;
  disabled?: boolean;
  onConfirm: () => void | Promise<void>;
  /** The trigger (a Button). */
  children: ReactNode;
}

/**
 * One confirmation language (docs/design-system/COMPONENT_CATALOGUE.md):
 * Popconfirm near the trigger for low-risk actions, a centred confirm
 * modal for destructive or irreversible ones; the same copy shape and
 * button types everywhere. Never `window.confirm`.
 */
export function ConfirmAction({
  title,
  consequence,
  okText,
  severity = "low",
  danger = true,
  disabled,
  onConfirm,
  children,
}: ConfirmActionProps) {
  const { confirm } = useFeedback();
  const label = okText ?? (danger ? "Delete" : "Confirm");

  if (severity === "high") {
    const open = () => confirm({ title, content: consequence, okText: label, danger, onOk: onConfirm });
    if (isValidElement<{ onClick?: (e: MouseEvent) => void; disabled?: boolean }>(children)) {
      // The trigger keeps its own semantics (a Button); we only intercept the click.
      return cloneElement(children as ReactElement<{ onClick?: (e: MouseEvent) => void; disabled?: boolean }>, {
        disabled: disabled || children.props.disabled,
        onClick: (e: MouseEvent) => {
          e.stopPropagation();
          if (!disabled) open();
        },
      });
    }
    return <>{children}</>;
  }
  return (
    <Popconfirm
      title={title}
      description={consequence}
      okText={label}
      cancelText="Cancel"
      okButtonProps={{ danger }}
      disabled={disabled}
      onConfirm={onConfirm}
    >
      {children}
    </Popconfirm>
  );
}
