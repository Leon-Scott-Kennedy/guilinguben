#!/usr/bin/env bash
# ============================================================
# 一键启动三端应用（E 轮 16.42）
# 前置：中间件容器（postgres/redis）与 Ollama 已就绪——容器生命周期由用户管理，
#       未就绪时本脚本仅提示并退出，不会自行 docker compose up。
# 用法：bash scripts/start-all.sh
# 产物：logs/java.log / ai-service.log / frontend.log + 对应 .pid（供 stop-all.sh 树杀）
# 幂等：某端已在运行（健康检查通过）则跳过，可重复执行。
# ============================================================
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

# 可覆盖配置：Anaconda 安装路径与 ai-service 环境名
ANACONDA_PATH="${ANACONDA_PATH:-C:/Users/LEONADA/anaconda3}"
AI_ENV_NAME="${AI_ENV_NAME:-torch_env}"

# 等待 HTTP 端点就绪：wait_http <url> <重试次数> <间隔秒>，就绪返回 0
wait_http() {
  local url="$1" tries="${2:-60}" interval="${3:-3}" n=0
  until curl -sf -o /dev/null --max-time 5 "$url"; do
    n=$((n + 1))
    if [ "$n" -ge "$tries" ]; then
      echo "  超时：$url 未就绪"
      return 1
    fi
    sleep "$interval"
  done
  echo "  就绪：$url"
  return 0
}

# 端口健康探测：已就绪返回 0（用于幂等跳过）
already_up() { curl -sf -o /dev/null --max-time 3 "$1"; }

# 依赖检查：docker / curl / mvn / npm / netstat
command -v docker >/dev/null 2>&1 || { echo "错误：docker 未找到，请先安装 Docker Desktop 并启动"; exit 1; }
command -v curl  >/dev/null 2>&1 || { echo "错误：curl 未找到"; exit 1; }
command -v mvn   >/dev/null 2>&1 || { echo "错误：mvn 未找到，请安装 JDK 17 + Maven 并加入 PATH"; exit 1; }
command -v npm   >/dev/null 2>&1 || { echo "错误：npm 未找到，请安装 Node.js 20+ 并加入 PATH"; exit 1; }

echo "==> 1/5 检查中间件容器（容器生命周期由用户管理，此处只读探测）"
RUNNING="$(docker ps --format '{{.Names}}' 2>/dev/null)"
echo "$RUNNING" | grep -qx "guilinguben-postgres" \
  || { echo "  guilinguben-postgres 未运行：请先执行 docker compose up -d postgres 后重跑本脚本"; exit 1; }
echo "$RUNNING" | grep -qx "guilinguben-redis" \
  || { echo "  guilinguben-redis 未运行：请先执行 docker compose up -d redis 后重跑本脚本"; exit 1; }
echo "  postgres / redis 容器均在运行"

echo "==> 2/5 检查 Ollama（11434）"
curl -sf -o /dev/null --max-time 5 http://localhost:11434/api/tags \
  || { echo "  Ollama 未就绪：请先启动 Ollama 并确保模型 qwen2.5:7b 已拉取"; exit 1; }
echo "  Ollama 就绪"

echo "==> 3/5 启动 Java 后端（8080）"
if already_up http://localhost:8080/api/health; then
  echo "  Java 已在运行，跳过"
else
  cd "$ROOT/services/java-backend"
  # -Dspring-boot.run.jvmArguments=-Dfile.encoding=UTF-8：Windows 下 JVM 默认编码为 GBK，
  # 日志重定向到文件后 logback ConsoleAppender 按 GBK 写入、按 UTF-8 读取即乱码（16.46）
  mvn spring-boot:run -Dspring-boot.run.jvmArguments=-Dfile.encoding=UTF-8 > "$LOG_DIR/java.log" 2>&1 &
  echo "$!" > "$LOG_DIR/java.pid"   # mvn 包装进程 PID，stop-all.sh 按树杀连带 java 子进程
  cd "$ROOT"
  wait_http "http://localhost:8080/api/health" 120 3 || echo "  Java 未在超时内就绪，请查看 logs/java.log"
fi

echo "==> 4/5 启动 ai-service（8001，torch_env）"
if already_up http://localhost:8001/health; then
  echo "  ai-service 已在运行，跳过"
else
  # 激活 torch_env 后启动；pydantic-settings 按启动工作目录读 .env，必须先 cd services/ai-service
  source "$ANACONDA_PATH/Scripts/activate" "$AI_ENV_NAME" 2>/dev/null \
    || { echo "  torch_env 激活失败：请检查 ANACONDA_PATH（当前 $ANACONDA_PATH，可用 ANACONDA_PATH=xxx 覆盖）"; exit 1; }
  cd "$ROOT/services/ai-service"
  # PYTHONIOENCODING=utf-8：Windows 上 Python 重定向 stdout 到文件时默认用 GBK 编码，
  # 业务 print 中的 ✓（\u2713）等非 GBK 字符会抛 UnicodeEncodeError 导致启动失败（16.44）
  PYTHONIOENCODING=utf-8 python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > "$LOG_DIR/ai-service.log" 2>&1 &
  echo "$!" > "$LOG_DIR/ai-service.pid"
  cd "$ROOT"
  wait_http "http://localhost:8001/health" 60 3 || echo "  ai-service 未在超时内就绪，请查看 logs/ai-service.log"
fi

echo "==> 5/5 启动前端（3000）"
if already_up http://localhost:3000; then
  echo "  前端已在运行，跳过"
else
  cd "$ROOT/services/frontend"
  npm run dev > "$LOG_DIR/frontend.log" 2>&1 &
  echo "$!" > "$LOG_DIR/frontend.pid"
  cd "$ROOT"
  # next dev 首次访问会按需编译，等待时间给足
  wait_http "http://localhost:3000" 60 3 || echo "  前端未在超时内就绪，请查看 logs/frontend.log"
fi

echo "==> 完成：三端健康状态"
already_up http://localhost:8080/api/health && echo "  Java    http://localhost:8080  OK" || echo "  Java    FAIL（见 logs/java.log）"
already_up http://localhost:8001/health        && echo "  AI      http://localhost:8001  OK" || echo "  AI      FAIL（见 logs/ai-service.log）"
already_up http://localhost:3000               && echo "  前端    http://localhost:3000  OK" || echo "  前端    FAIL（见 logs/frontend.log）"
echo "  日志目录：$LOG_DIR"
echo "  登录演示账号：admin / admin123"
