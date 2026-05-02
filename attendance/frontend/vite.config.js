import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  base: './',
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          reactVendor: ['react', 'react-dom', 'react-router-dom'],
          mapVendor: ['@vis.gl/react-google-maps'],
          faceVendor: ['@vladmandic/face-api'],
          pdfVendor: ['jspdf', 'jspdf-autotable'],
          socketVendor: ['socket.io-client']
        }
      }
    }
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['pwa-192x192.png', 'pwa-512x512.png', 'favicon.ico', 'apple-touch-icon.png', 'masked-icon.svg'],
      manifest: {
        name: 'Berkeley Workforce 360',
        short_name: 'Berkeley Workforce 360',
        description: 'Berkeley Workforce 360 Employee Attendance and Tracking',
        theme_color: '#ffffff',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png'
          }
        ]
      }
    })
  ],
  server: {
    host: true,
    port: 5173,
    allowedHosts: ['attendance.berkeleyuae.com'],
    proxy: {
      '/api': {
        target: 'http://api:3000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/iclock': {
        target: 'http://api:3000',
        changeOrigin: true
      },
      '/socket.io': {
        target: 'http://api:3000',
        ws: true
      }
    }
  }
})
