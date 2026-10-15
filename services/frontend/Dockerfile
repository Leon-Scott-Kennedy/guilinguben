# ============================================================
# 前端容器化（E 轮 16.42 方案丙可选资产，默认不启用）
# 多阶段构建：依赖安装 → next build → 精简运行层（next start 生产模式）。
# next.config.ts 未启用 output: standalone，运行层需拷贝 node_modules + .next + public。
# 运行方式：docker compose up -d frontend（见根 docker-compose.yml 注释块），
# 或单独构建：cd services/frontend && docker build -t guilinguben-frontend .
# 注意：src/lib/api.ts 中后端地址 http://localhost:8080 是浏览器侧请求，
#   浏览器仍在宿主机访问，容器化无需修改。
# ============================================================

# ---- 依赖层 ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- 构建层 ----
FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# ---- 运行层 ----
FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "run", "start"]
