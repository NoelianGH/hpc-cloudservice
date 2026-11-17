/** @type {import('next').NextConfig} */
const dev = process.env.NODE_ENV !== "production";

// Content-Security-Policy: hanya muat skrip/gaya dari situs ini, gambar avatar dari GitHub /
// ui-avatars, tanpa iframe pihak lain. 'unsafe-inline' untuk skrip diperlukan Next.js 14 (skrip
// hidrasi inline); 'unsafe-eval' dan websocket hanya saat 'next dev'.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://github.com https://avatars.githubusercontent.com https://ui-avatars.com",
  "font-src 'self' data:",
  `connect-src 'self'${dev ? " ws: wss:" : ""}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  // HSTS hanya berlaku bila situs dibuka lewat HTTPS (browser mengabaikannya di HTTP)
  ...(dev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]),
];

const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  env: {
    NEXT_PUBLIC_COORDINATOR_URL: process.env.COORDINATOR_URL || "http://localhost:8000",
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  webpack: (config, { dev: isDev }) => {
    if (isDev) {
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
};

export default nextConfig;
