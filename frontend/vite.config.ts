import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const productionDemoModule = fileURLToPath(new URL("./src/api/demo-disabled.ts", import.meta.url));

export default defineConfig(({ command }) => ({
  plugins: [react()],
  resolve: {
    alias: command === "build"
      ? [{ find: /(?:\.\/|\.\.\/api\/)demo$/, replacement: productionDemoModule }]
      : [],
  },
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
}));
