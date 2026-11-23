/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required for the Dockerfile's standalone output mode
  output: 'standalone',

  reactStrictMode: true,

  // Allow the container to bind on any host inside Docker
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  },
};

module.exports = nextConfig;