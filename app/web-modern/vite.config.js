import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import {cpSync,rmSync} from 'node:fs'
import {fileURLToPath} from 'node:url'

export default defineConfig({
  plugins: [svelte(), {name:'package-desktop-dashboard', closeBundle(){
    const src=fileURLToPath(new URL('../web/dist/',import.meta.url));
    const dest=fileURLToPath(new URL('../brandforge_assets/dashboard/',import.meta.url));
    rmSync(dest,{recursive:true,force:true});cpSync(src,dest,{recursive:true});
  }}],
  base: './', // FIX: Relative base for file:// and /sales/ and /dist/ - production-ready, works everywhere
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  },
  build: {
    outDir: '../web/dist',
    emptyOutDir: true,
    assetsDir: 'assets'
  }
})
