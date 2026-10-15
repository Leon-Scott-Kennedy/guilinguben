"""进程内调用指标收集（⑥16.41）：接口层与 LLM 层计数 + 耗时累加，/metrics 接口暴露 JSON 快照。

设计取舍：MVP 不引入 Prometheus 等外部监控（本地单机无采集基建，收益低），
进程内线程安全聚合即可满足"调用指标"验收；指标随进程重启清零（与 Java 端
会话缓冲同生命周期），持久化指标不在 MVP 范围（方案 B 默认取舍）。
"""
import threading
import time
from collections import deque

_lock = threading.Lock()
_started_at = time.time()

# LLM 调用点最近明细条数（方案 B：最近 20 次，供排障观察模型调用耗时抖动）
RECENT_KEEP = 20

# 接口层：name -> {"total", "success", "fail", "duration_ms", "max_duration_ms"}
_interface_stats: dict = {}
# LLM 层：name -> {"total", "fail", "duration_ms", "recent": deque}
_llm_stats: dict = {}


def record_interface(name: str, success: bool, duration_ms: float) -> None:
    """记录一次对外接口调用（analyze / analyze_stream / explain）"""
    with _lock:
        stat = _interface_stats.setdefault(
            name, {"total": 0, "success": 0, "fail": 0, "duration_ms": 0.0, "max_duration_ms": 0.0}
        )
        stat["total"] += 1
        if success:
            stat["success"] += 1
        else:
            stat["fail"] += 1
        stat["duration_ms"] += duration_ms
        stat["max_duration_ms"] = max(stat["max_duration_ms"], duration_ms)


def record_llm(name: str, success: bool, duration_ms: float) -> None:
    """记录一次本地模型调用（chat_with_tools / chat_guardrail / chat_final_answer / summarize_history / local_llm_response）"""
    with _lock:
        stat = _llm_stats.setdefault(
            name, {"total": 0, "fail": 0, "duration_ms": 0.0, "recent": deque(maxlen=RECENT_KEEP)}
        )
        stat["total"] += 1
        if not success:
            stat["fail"] += 1
        stat["duration_ms"] += duration_ms
        stat["recent"].append({"success": success, "duration_ms": round(duration_ms, 1)})


def metrics_snapshot() -> dict:
    """指标快照：接口层含成功率/平均与最长耗时，LLM 层含失败数/平均耗时/最近 20 次明细"""
    with _lock:
        interfaces = {}
        for name, stat in _interface_stats.items():
            total = stat["total"]
            interfaces[name] = {
                "total": total,
                "success": stat["success"],
                "fail": stat["fail"],
                "success_rate": round(stat["success"] / total, 4) if total else 1.0,
                "avg_duration_ms": round(stat["duration_ms"] / total, 1) if total else 0.0,
                "max_duration_ms": round(stat["max_duration_ms"], 1),
            }
        llm_calls = {}
        for name, stat in _llm_stats.items():
            total = stat["total"]
            llm_calls[name] = {
                "total": total,
                "fail": stat["fail"],
                "avg_duration_ms": round(stat["duration_ms"] / total, 1) if total else 0.0,
                "recent": list(stat["recent"]),
            }
    return {
        "uptime_seconds": round(time.time() - _started_at, 1),
        "interfaces": interfaces,
        "llm_calls": llm_calls,
    }
