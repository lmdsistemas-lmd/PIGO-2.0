import { defineConfig } from "vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import babel from "@rolldown/plugin-babel";

export default defineConfig({
  plugins: [
    react(),
    babel({
      presets: [reactCompilerPreset()],
    }),
  ],
  server: {
    host: "0.0.0.0",
    port: 5176,
    strictPort: true,
    allowedHosts: [
      "pigo.lmdsistemasdev.qzz.io",
    ],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:4000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 4176,
    allowedHosts: [
      "pigo.lmdsistemasdev.qzz.io",
    ],
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
