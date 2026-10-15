"""历史上下文摘要化（多轮记忆治理，16.32）

滑动窗口 + LLM 摘要：Java 注入的最近 5 轮原文中，最近 1 轮保留原文（指代解析需要，
如"它的组成是什么？"依赖上一轮提到的方剂名），更早轮次压缩为 LLM 要点摘要，
控制 system prompt 的 token 膨胀（B5 实测 5 轮原文拼接可达 1000+ 字）。

增量缓存：同会话连续对话时，新请求需要的摘要 = 上次已生成摘要 + 新增轮次，
把"旧摘要 + 新轮原文"合并后重新提炼一次（每请求最多一次摘要 LLM 调用，
且缓存命中的常态路径零 LLM 开销）；单轮对话（历史 ≤1 轮）零 LLM 开销。
缓存为进程内存（session_id 为键），重启后首次请求重新摘要（降级可接受）。
"""
import re
import threading
from typing import Dict, List, Tuple

from app.agent.llm import summarize_history

# 保留原文的最近轮数：指代追问依赖最近一轮原文
MAX_RECENT_RAW_ROUNDS = 1
# 摘要失败时的降级：每轮问答截断字数
FALLBACK_TRUNCATE = 80

# session_id -> (摘要覆盖的轮数, 摘要文本)；进程内存缓存，重启丢失后重新摘要（可接受）
_cache: Dict[str, Tuple[int, str]] = {}
_cache_lock = threading.Lock()

# Java 端拼接格式：每轮 "User: xxx\nAI: yyy" + 空行分隔；answer 内可能含换行，
# 因此以 "User:" 作为轮次边界切分（Java 拼接不会在 answer 内产生行首 User:）
_ROUND_PATTERN = re.compile(r"User:\s*(.*?)\nAI:\s*(.*?)(?=\n+User:|\Z)", re.S)


def _parse_rounds(history_context: str) -> List[Tuple[str, str]]:
    """解析历史上下文为 [(问题, 回答), ...] 轮次列表（按 Java 拼接格式）"""
    rounds = []
    for user_text, ai_text in _ROUND_PATTERN.findall(history_context):
        user = " ".join(user_text.strip().split())
        ai = " ".join(ai_text.strip().split())
        if user or ai:
            rounds.append((user, ai))
    return rounds


def _format_rounds(rounds: List[Tuple[str, str]]) -> str:
    """轮次列表格式化为 User:/AI: 文本（与 Java 拼接格式一致，供摘要与注入）"""
    lines = []
    for user, ai in rounds:
        lines.append(f"User: {user}")
        lines.append(f"AI: {ai}")
    return "\n".join(lines)


def _truncated(rounds: List[Tuple[str, str]]) -> str:
    """摘要失败降级：原文截断（保留问答开头，控制上下文长度）"""
    lines = []
    for user, ai in rounds:
        lines.append(f"User: {user[:FALLBACK_TRUNCATE]}")
        lines.append(f"AI: {ai[:FALLBACK_TRUNCATE]}")
    return "\n".join(lines)


def compress_history_context(session_id: str, history_context: str) -> str:
    """把 Java 注入的历史原文压缩为：更早轮次摘要 + 最近 MAX_RECENT_RAW_ROUNDS 轮原文

    返回可直接替换 history_context 注入 system prompt 的文本；
    历史 ≤ MAX_RECENT_RAW_ROUNDS 轮时原样返回（零 LLM 开销）。
    """
    rounds = _parse_rounds(history_context)
    if len(rounds) <= MAX_RECENT_RAW_ROUNDS:
        return history_context

    target_n = len(rounds) - MAX_RECENT_RAW_ROUNDS  # 需要摘要覆盖的轮数

    with _cache_lock:
        cached_n, cached_summary = _cache.get(session_id, (0, ""))
        if cached_n == target_n:
            summary = cached_summary  # 缓存命中（连续对话常态路径），零 LLM 开销
        elif 0 < cached_n < target_n:
            # 增量更新：旧摘要 + 新增轮次原文合并后重新提炼一次
            merged = cached_summary + "\n" + _format_rounds(rounds[cached_n:target_n])
            new_summary = summarize_history(merged)
            summary = (
                new_summary
                if new_summary
                else cached_summary + "\n" + _truncated(rounds[cached_n:target_n])
            )
        else:
            # 首次或缓存失效：全量摘要
            new_summary = summarize_history(_format_rounds(rounds[:target_n]))
            summary = new_summary if new_summary else _truncated(rounds[:target_n])
        _cache[session_id] = (target_n, summary)

    recent_text = _format_rounds(rounds[target_n:])
    if not summary.strip():
        return history_context  # 摘要为空（异常极端情况）：退回原文，保证功能可用
    return (
        f"历史对话要点摘要（更早轮次，仅供理解对话连续性，不构成证据）：\n{summary}\n"
        f"最近一轮对话原文：\n{recent_text}"
    )
