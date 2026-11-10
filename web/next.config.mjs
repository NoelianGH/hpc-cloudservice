/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_COORDINATOR_URL: process.env.COORDINATOR_URL || "http://localhost:8000",
  },
};

export default nextConfig;

