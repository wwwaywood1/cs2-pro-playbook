import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// HashRouter + relative base: the build can be served from any GitHub Pages
// sub-path without server-side rewrites.
export default defineConfig({
  base: "./",
  plugins: [react()],
});
