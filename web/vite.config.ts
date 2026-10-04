import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react()],
  // GitHub Pages serves the site from https://<user>.github.io/jobwatch/, so production
  // builds need that path prefix. `npm run dev` stays at the root.
  base: command === 'build' ? '/jobwatch/' : '/',
}))
