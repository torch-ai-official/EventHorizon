/** @type {import('next').NextConfig} */
import withPWA from 'next-pwa'
import path from 'path'

const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  
  // ⭐ Configuracao do Turbopack para o Next.js 16
  turbopack: {
    // Define a raiz do projeto para resolver o aviso do lockfile
    root: path.join(process.cwd()),
  },
  
  // ⭐ Rewrites para conectar ao backend FastAPI
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
      {
        source: '/dashboard/stats',
        destination: 'http://localhost:8000/dashboard/stats',
      },
      {
        source: '/trader/stats',
        destination: 'http://localhost:8000/trader/stats',
      },
    ]
  },
}

// ⭐ Configuracao do PWA
export default withPWA({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
})(nextConfig)