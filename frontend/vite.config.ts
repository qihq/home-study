import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', setupFiles: './src/testSetup.ts', globals: true, testTimeout: 15_000 },
  server: { proxy: { '/api': 'http://127.0.0.1:8001' } },
})
