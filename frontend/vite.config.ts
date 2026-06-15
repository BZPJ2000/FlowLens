import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiPort = process.env.POLTAISHOW_API_PORT || "8879";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: true,
      },
    },
  },
});
