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
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
