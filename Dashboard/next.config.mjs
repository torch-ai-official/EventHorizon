/** @type {import('next').NextConfig} */
import withPWA from 'next-pwa'
import path from 'path'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

console.log('🔧 API_URL:', API_URL)  // ⭐ VERIFIQUE SE ESTÁ CORRETO

const nextConfig = {
  // ⭐ REMOVA OU COMENTE 'output: export'
  output: 'export',  // ← COMENTE ESTA LINHA
  
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  
  turbopack: {
    root: path.join(process.cwd()),
  },
  
  // ⭐ Adicione o host para permitir acesso externo

  
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${API_URL}/:path*`,
      },
      {
        source: '/status',
        destination: `${API_URL}/status`,
      },
      {
        source: '/dashboard/stats',
        destination: `${API_URL}/dashboard/stats`,
      },
      {
        source: '/trader/stats',
        destination: `${API_URL}/trader/stats`,
      },
      {
        source: '/chatbot',
        destination: `${API_URL}/chatbot`,
      },
    ]
  },
}

export default withPWA({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
})(nextConfig)