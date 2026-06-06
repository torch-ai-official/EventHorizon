/** @type {import('next').NextConfig} */
import withPWA from 'next-pwa'
import path from 'path'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const nextConfig = {
  output: 'export',              // ✅ JÁ TEM, está correto
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  turbopack: {
    root: path.join(process.cwd()),
  },
  // ⚠️ IMPORTANTE: REMOVA a seção `rewrites` por completo
  // async rewrites() { ... }  <-- COMENTE OU APAGUE ISSO
}

export default withPWA({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
})(nextConfig)