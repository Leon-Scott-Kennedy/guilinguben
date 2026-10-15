# 部署手册（E 轮 16.42 · 编排方案丙）

> 编排取舍（方案丙）：**Docker Compose 管中间件，启动脚本管三端应用**；
> 三端容器化为可选资产（面试展示用），默认不启用。
> 容器启停/迁移等生命周期操作一律由部署方执行，脚本仅做只读探测。

## 1. 架构总览

| 组件 | 运行方式 | 端口 | 说明 |
| --- | --- | --- | --- |
| postgres / redis | Docker Compose（healthcheck） | 5432 / 6379 | 日常必启 |
| Java 后端 | scripts/start-all.sh（mvn spring-boot:run） | 8080 | 健康：`GET /api/health` |
| ai-service | scripts/start-all.sh（uvicorn + torch_env） | 8001 | 健康：`GET /health` |
| 前端 | scripts/start-all.sh（next dev） | 3000 | 页面入口 |
| Ollama | 宿主机进程（qwen2.5:7b） | 11434 | 三端与容器的共同依赖 |
| rabbitmq | Compose（`--profile mq`） | 5672/15672 | 阶段五待办，默认不拉起 |
| milvus 栈 | Compose（`--profile milvus`） | 19530 等 | 已切 chroma，默认不拉起 |

## 2. 环境要求

- Docker Desktop（Windows）、Git Bash
- JDK 17 + Maven（PATH 中可用 `mvn`）
- Node.js 20+（PATH 中可用 `npm`）
- Anaconda（默认 `C:/Users/<user>/anaconda3`，含 `torch_env` 环境，可用 `ANACONDA_PATH`/`AI_ENV_NAME` 覆盖）
- Ollama 已启动且已拉取 `qwen2.5:7b`

## 3. 首次初始化

1. 启动中间件容器：

   ```bash
   docker compose up -d postgres redis
   ```

2. （历史环境一次性，本项目已完成 2026-09-20）postgres 容器管理化迁移——早期
   `docker run` 容器挂匿名卷，与 compose 的 named volume `postgres_data` 不一致时，
   按 E 轮方案第 1 部分执行备份→重建→恢复（详见交接文件 E 轮小节）。

3. 启动三端：

   ```bash
   bash scripts/start-all.sh
   ```

## 4. 日常操作

| 操作 | 命令 | 说明 |
| --- | --- | --- |
| 一键启动三端 | `bash scripts/start-all.sh` | 幂等：已就绪的端自动跳过；日志与 PID 文件在 `logs/` |
| 一键停止三端 | `bash scripts/stop-all.sh` | 只停应用进程，不动任何容器 |
| 查看日志 | `tail -f logs/java.log` 等 | `java.log` / `ai-service.log` / `frontend.log` |

start-all.sh 前置检查（未就绪仅提示并退出，不自行拉起容器/服务）：
中间件容器 → Ollama → 逐端启动并等待健康端点。

stop-all.sh 停止策略（16.45 强化）：读 `logs/*.pid` 优先 `taskkill //F //T` 树杀、
失败时 kill 兜底；随后**无条件**按端口 8080/8001/3000 扫描残留（netstat 取 Windows PID）树杀——
以“端口释放”为最终判据（无 PID 文件的应用、mvn/npm 包装进程被杀后的 java/node 孤儿均被兜住）。

## 5. 验证清单

```bash
curl -s http://localhost:8080/api/health   # Java 健康
curl -s http://localhost:8001/health       # ai-service 健康
curl -s http://localhost:11434/api/tags    # Ollama 就绪
docker compose ps                          # postgres/redis healthy
```

浏览器打开 http://localhost:3000 ，登录演示账号 `admin / admin123`，问答一轮验证三端链路。

## 6. 中间件按需扩展（profiles）

```bash
# RabbitMQ（阶段五待办接线后启用）
docker compose --profile mq up -d rabbitmq

# milvus 栈（切回 milvus 后端时启用；分三步：etcd/minio → minio-setup → milvus）
docker compose --profile milvus up -d etcd minio && sleep 12 \
  && docker compose --profile milvus up -d minio-setup && sleep 6 \
  && docker compose --profile milvus up -d milvus
```

## 7. 三端容器化（可选资产）

默认注释在 `docker-compose.yml` 末尾，启用方式：取消注释后执行

```bash
docker compose up -d --build java-backend ai-service frontend
```

关键设计（详见各 Dockerfile 头注释）：

- **java-backend**：maven 多阶段构建；`SPRING_DATASOURCE_URL` / `SPRING_DATA_REDIS_HOST` /
  `AI_SERVICE_BASEURL` 环境变量指向 `host.docker.internal`（Spring relaxed binding 覆盖 application.yml）。
- **ai-service**：构建上下文为项目根；容器内 `BASE_DIR`（config.py `parents[3]`）为 `/`，
  故挂载 `./models:/models`、`./data:/data`、`./guilinguben.pdf:/guilinguben.pdf`；
  本机 `.env` 的 Windows 绝对路径由 ENV 覆盖（`LLM_BASE_URL`、`VECTOR_BACKEND=chroma`、
  `CHROMA_PERSIST_DIR=/data/chroma_index` 等，环境变量优先级高于 .env）。
- **frontend**：next 多阶段构建 + `next start`；`src/lib/api.ts` 的 `http://localhost:8080`
  是浏览器侧请求，浏览器仍在宿主机，无需修改。
- `extra_hosts: host.docker.internal:host-gateway`：兼容 Linux 环境（Windows/Mac Docker Desktop 自带）。

## 8. FAQ

- **start-all.sh 提示容器未运行**：先执行 `docker compose up -d postgres redis` 后重跑。
- **torch_env 激活失败**：`ANACONDA_PATH=/path/to/anaconda3 bash scripts/start-all.sh` 覆盖路径。
- **前端启动后 3000 未就绪**：next dev 首次访问按需编译，脚本已给足等待；仍失败看 `logs/frontend.log`。
- **端口被占用**：先 `bash scripts/stop-all.sh` 兜底清理（注意：它会停掉占用
  8080/8001/3000 的进程树，无论是否本脚本启动——如端口被其他程序占用请先迁移该程序）。
- **Java 连 postgres 报密码认证失败**：① 先确认连的是 Docker 容器库——Windows 上 `localhost`
  优先解析为 IPv6 `::1`，可能撞上 WSL 转发，JDBC URL 已用 `127.0.0.1` 规避（16.43）；
  ② 若密码仍不对：命名卷复用时 `POSTGRES_PASSWORD` 不生效（仅空卷首次 initdb 生效），
  执行 `docker exec guilinguben-postgres psql -U guilinguben -d guilinguben -c "ALTER USER guilinguben WITH PASSWORD '123';"` 三方对齐。
- **日志中文乱码 / ai-service 启动报 UnicodeEncodeError**：脚本已内置修复（Python 加
  `PYTHONIOENCODING=utf-8`、Java 加 `-Dfile.encoding=UTF-8`，16.44/16.46）；手动启动时
  若复现，按同思路给对应进程加编码参数。
- **容器内访问宿主机**：一律用 `host.docker.internal`，不用 `localhost`（容器内 localhost 指向容器自身）。
