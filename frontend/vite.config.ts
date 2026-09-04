import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
