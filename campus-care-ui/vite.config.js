import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],

  build: {
    // Element Plus 全量引入后单包偏大（约 1MB，gzip 后 350KB）。
    // 把它和 Vue 运行时分到独立 chunk：总体积不变，但浏览器能并行下载且长期缓存，
    // 之后只改业务代码时，这两个大包不会失效。
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router'],
          element: ['element-plus'],
        },
      },
    },
  },

  server: {
    port: 5173,
    // 开发期把 /api 代理到 Java 服务。
    // 这样前端代码里永远写相对路径，既不用依赖后端的 CORS 配置，
    // 也不会出现「本地能跑、上线就跨域」的问题。
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
})
