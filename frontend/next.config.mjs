/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Browser code calls the backend through same-origin `/api/*`. Forwarding
  // is handled by the catch-all route handler at `app/api/[...path]/route.ts`,
  // which disables HTTP keep-alive and retries once on transient connect
  // errors so backend container rebuilds don't break the running frontend.
};

export default nextConfig;
