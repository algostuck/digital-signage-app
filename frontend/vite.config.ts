import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // `@/design-system` is the one import path for the design system
    // (docs/design-system/DESIGN_SYSTEM_USAGE.md); mirrors tsconfig `paths`.
    alias: { "@": "/src" },
  },
  build: {
    // The antd vendor chunk is ~450kB gzipped by design: one immutable,
    // long-cached file instead of antd fragments duplicated across page
    // chunks. App-code deploys never invalidate it.
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        // Keep the heavyweight vendors in their own long-lived cacheable
        // chunks; app code changes then never invalidate them.
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          antd: ["antd"],
          icons: ["@ant-design/icons"],
          query: ["@tanstack/react-query"],
        },
      },
    },
  },
  // The dashboard route lazy-loads the chart and map libraries. Left to
  // discovery, Vite re-optimises dependencies mid-session when it first
  // sees them, which leaves two copies of the AntV runtime alive in one page
  // and every chart throwing. Declaring them here bundles them up front
  // with everything else, once.
  optimizeDeps: {
    include: ["@ant-design/plots", "leaflet", "react-leaflet"],
    esbuildOptions: {
      // Match the production build target so the AntV engine's classes are
      // lowered identically in both; see the plugin below for the rest.
      target: "es2020",
      plugins: [
        {
          // Dev only (pre-bundling does not run for production builds).
          // `@ant-design/charts-util`'s React renderer loads react-dom
          // lazily and flags itself "initialised" *before* the import
          // resolves, so concurrent renders from one page of charts see the
          // flag, find no `createRoot`, and throw "ReactDOM.render not
          // available" — every plot blank, in dev only, because the
          // production bundle happens to serialise those calls. This swaps
          // in the same API with a static import and no race.
          name: "plots-react-render-fix",
          setup(build) {
            build.onLoad({ filter: /charts-util[\\/]es[\\/]react[\\/]render\.js$/ }, () => ({
              loader: "js",
              contents: `
import { createRoot } from "react-dom/client";
const MARK = "__rc_react_root__";
export async function render(node, container) {
  if (!container[MARK]) container[MARK] = createRoot(container);
  container[MARK].render(node);
}
export async function unmount(container) {
  container[MARK]?.unmount?.();
  delete container[MARK];
}
`,
            }));
          },
        },
      ],
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  // `vite preview` serves the production build; give it the same proxy so
  // the built app can be exercised against the local API.
  preview: {
    port: 4173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
