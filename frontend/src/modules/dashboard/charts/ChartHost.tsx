import { useEffect, useRef, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";

/**
 * Renders a chart element in a React root of its own.
 *
 * Why: in development React 18's StrictMode mounts, unmounts and remounts
 * every component. `@ant-design/plots` creates its G2 chart in an effect,
 * so the first instance is destroyed while G2's asynchronous render is
 * still running and the page fills with "ownerDocument of null" errors
 * and blank plots. StrictMode cannot be switched off for a subtree, but a
 * separate root is outside it, so the chart mounts exactly once — in
 * development and production alike. Charts take their colours as props,
 * so losing the antd context here costs nothing.
 *
 * StrictMode still double-runs *this* component's effects; the unmount is
 * deferred one tick and cancelled if the effect re-runs, so the fake
 * unmount never destroys the root.
 */
export function ChartHost({ children, height }: { children: ReactElement; height: number }) {
  const container = useRef<HTMLDivElement>(null);
  const state = useRef<{ root: Root; unmountTimer: number | null } | null>(null);

  useEffect(() => {
    const el = container.current;
    if (!el) return;
    if (state.current?.unmountTimer != null) {
      window.clearTimeout(state.current.unmountTimer);
      state.current.unmountTimer = null;
    }
    if (!state.current) state.current = { root: createRoot(el), unmountTimer: null };
    return () => {
      const current = state.current;
      if (!current) return;
      current.unmountTimer = window.setTimeout(() => {
        current.root.unmount();
        if (state.current === current) state.current = null;
      }, 0);
    };
  }, []);

  useEffect(() => {
    state.current?.root.render(children);
  });

  return <div ref={container} style={{ height }} />;
}
