import { createContext, useContext, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

/** One breadcrumb entry. The last entry is the current page and is
 * rendered as text; earlier entries with `to` are links. */
export interface Crumb {
  label: string;
  to?: string;
}

/**
 * The design system does not know the application's navigation tree, so
 * the shell injects a resolver (built from `src/config/navigation.tsx`)
 * and `PageHeader` derives "Module › Page" from the current route unless
 * a page supplies its own trail (detail pages add the entity).
 *
 * Standard (docs/design-system/ANTD_REFERENCE_ANALYSIS.md §3.1): pages
 * under a module show `Module / Page`; top-level pages show nothing;
 * detail pages show `Module / Page / Entity` (≤ 3 levels).
 */
export type BreadcrumbResolver = (pathname: string) => Crumb[];

const BreadcrumbContext = createContext<BreadcrumbResolver>(() => []);

export function BreadcrumbProvider({
  resolve,
  children,
}: {
  resolve: BreadcrumbResolver;
  children: ReactNode;
}) {
  return <BreadcrumbContext.Provider value={resolve}>{children}</BreadcrumbContext.Provider>;
}

/** Breadcrumbs for the current route from the shell's resolver. */
export function useBreadcrumbs(): Crumb[] {
  const resolve = useContext(BreadcrumbContext);
  const { pathname } = useLocation();
  return resolve(pathname);
}
