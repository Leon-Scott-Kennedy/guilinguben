#!/usr/bin/env bash
# ============================================================
# 一键停止三端应用（E 轮 16.42）
# 只停应用进程，不动任何容器——容器生命周期由用户管理。
# 用法：bash scripts/stop-all.sh
# 原理（16.45 强化）：① 读 logs/*.pid（start-all.sh 记录），taskkill //F //T 树杀，
#        失败时 kill -9 兜底（覆盖 MSYS 伪 PID 场景）；② 无论 PID 是否可读/是否成功，
#        都按监听端口 8080/8001/3000 扫描残留（netstat Windows PID）树杀——
#        kill -9 只杀 MSYS 包装进程，mvn/npm 的 java/node 子进程成孤儿、或
#        应用非本脚本启动（无 PID 文件）时都靠端口扫描兜底。
# ============================================================
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"

# 停止单个进程：优先 taskkill 树杀（原生 Windows PID），失败 kill -9 兜底
stop_pid() {
  local pid="$1" label="$2"
  if command -v taskkill >/dev/null 2>&1; then
    if taskkill //PID "$pid" //F //T >/dev/null 2>&1; then
      echo "  $label：已停止（taskkill 树杀 PID $pid）"
      return 0
    fi
  fi
  if kill -9 "$pid" >/dev/null 2>&1; then
    echo "  $label：已停止（kill -9 PID $pid）"
    return 0
  fi
  return 1
}

# 停止某一端：PID 文件优先尝试，端口扫描无条件兜底（16.45 强化）
stop_endpoint() {
  local name="$1" port="$2" pidfile="$LOG_DIR/$1.pid" pid
  if [ -f "$pidfile" ]; then
    pid="$(tr -d '[:space:]' < "$pidfile")"
    rm -f "$pidfile"
    if [ -n "$pid" ]; then
      stop_pid "$pid" "$name（PID 文件）" || echo "  $name：PID $pid 已失效"
    else
      echo "  $name：PID 文件为空"
    fi
  else
    echo "  $name：无 PID 文件（非本脚本启动），直接按端口扫描"
  fi
  # 无条件端口兜底：kill -9 伪 PID 只杀 MSYS 包装进程，mvn/npm 的 java/node 子进程
  # 会成为孤儿继续监听；非本脚本启动的进程更无 PID 文件——都靠端口扫描树杀
  local pids
  pids="$(netstat -ano 2>/dev/null | awk -v p=":$port " '$0 ~ p && /LISTENING/ {print $NF}' | sort -u)"
  if [ -z "$pids" ]; then
    echo "  $name：端口 $port 无监听（已释放）"
    return
  fi
  for pid in $pids; do
    stop_pid "$pid" "$name（端口 $port 残留）"
  done
}

echo "==> 停止三端应用（不动容器）"
stop_endpoint java       8080
stop_endpoint ai-service 8001
stop_endpoint frontend   3000

echo "==> 完成：三端应用已停止，postgres/redis 等容器保持原状"
