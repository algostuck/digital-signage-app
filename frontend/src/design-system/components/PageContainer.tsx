import { Flex } from "antd";
import { createContext, useContext, type ReactNode } from "react";
import { SPACE } from "../tokens/scale";
import { PageHeader, type PageHeaderProps } from "./PageHeader";

/** True inside a PageContainer, so a standalone PageHeader can keep its
 * own bottom spacing while the container supplies the rhythm. */
const InsideContainer = createContext(false);
export function useInsidePageContainer(): boolean {
  return useContext(InsideContainer);
}

interface PageContainerProps extends PageHeaderProps {
  /** Filter row rendered between the header and the content. */
  filters?: ReactNode;
  /** `narrow` caps forms and settings at 960px; `full` is the default. */
  width?: "full" | "narrow";
  children: ReactNode;
}

/**
 * The vertical rhythm of every business page
 * (docs/design-system/DESIGN_SYSTEM_USAGE.md §1): header → filters →
 * sections, 24px apart. Pages add no margins of their own.
 */
export function PageContainer({ filters, width = "full", children, ...header }: PageContainerProps) {
  return (
    <Flex
      vertical
      gap={SPACE.lg}
      style={width === "narrow" ? { maxWidth: 960, marginInline: "auto", width: "100%" } : undefined}
    >
      <InsideContainer.Provider value>
        <PageHeader {...header} />
        {filters}
        {children}
      </InsideContainer.Provider>
    </Flex>
  );
}
