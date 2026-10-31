import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Served as plain files by the Python process — no Node runtime at runtime.
  output: "export",

  // Static export cannot run the image optimizer.
  images: { unoptimized: true },

  // Emit /console/index.html so FastAPI's StaticFiles can serve clean URLs.
  trailingSlash: true,

  // The dashboard is mounted at the server root.
  basePath: "",

  // Fail the build loudly rather than shipping a broken dashboard.
  // (Next 16 no longer runs ESLint inside `next build`; use `npm run lint`.)
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
