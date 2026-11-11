/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const api = process.env.MANDATE_API_URL || "http://127.0.0.1:8001";
    return [{ source: "/v1", destination: `${api}/v1` }];
  },
};

export default nextConfig;
