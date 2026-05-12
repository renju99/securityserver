import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

const __dirname = dirname(fileURLToPath(import.meta.url))
const appVersion = JSON.parse(readFileSync(join(__dirname, 'package.json'), 'utf8')).version || '0.0.0'

// Web / Docker: use '/' so /hr and other deep routes still load /assets/*.js (not /hr/assets/…).
// Cordova: build with VITE_BASE=./ (see scripts/sync-frontend-to-cordova-www.sh).
const publicBase = process.env.VITE_BASE === './' || process.env.VITE_BASE === 'relative' ? './' : '/'

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  base: publicBase,
  build: {
    sourcemap: false,
    // Face recognition is intentionally isolated into an on-demand vendor chunk.
    chunkSizeWarningLimit: 1400,
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
      workbox: {
        navigateFallbackDenylist: [
          /^\/socket\.io/,
          /^\/api\//,
          /^\/iclock\//,
          /^\/assets\//,
          /^\/hr\/assets\//,
          // Avoid serving the SPA shell for direct navigations to static URLs (e.g. opening a chunk in a tab).
          /\.(?:js|mjs|css|map|json|webmanifest|woff2?)(?:\?|$)/i,
        ],
      },
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
      '/auth': {
        target: 'http://api:3000',
        changeOrigin: true,
      },
      '/hr': {
        target: 'http://api:3000',
        changeOrigin: true,
        // Same issue as prod nginx: /hr must not swallow Vite chunks when base is './' and URL is /hr/…
        bypass(req) {
          const u = req.url ?? ''
          if (u.startsWith('/hr/assets/')) return u.replace(/^\/hr/, '') || u
          if (
            /^\/hr\/registerSW\.js(\?|$)/.test(u) ||
            /^\/hr\/manifest\.webmanifest(\?|$)/.test(u) ||
            /^\/hr\/sw\.js(\?|$)/.test(u) ||
            /^\/hr\/dev-sw\.js(\?|$)/.test(u) ||
            /^\/hr\/workbox-/.test(u)
          ) {
            return u.replace(/^\/hr/, '') || u
          }
        },
      },
      '/attendance': {
        target: 'http://api:3000',
        changeOrigin: true,
      },
      '/api/biometrics': {
        target: 'http://api:3000',
        changeOrigin: true,
      },
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
