"""Agent 图状态定义"""
from typing import Any, Dict, List, TypedDict


class AgentState(TypedDict):
    """LangGraph 状态机的核心状态结构（B3 版本：围栏升级 + 工具循环 + 截断收敛）

    B4 将引入会话检查点，把 messages 持久化到图状态存储。
    """

    question: str                    # 当前用户问题
    session_id: str                  # 会话标识（多轮摘要缓存键，查缺补漏②引入）
    history_context: str             # Java 端拼装的历史上下文（最近 5 轮 User/AI 对话）
    strict_mode: bool                # 严格模式开关（注入 system prompt，控制证据强制要求）
    top_k: int                       # 检索条数
    messages: List[Dict[str, Any]]   # Ollama /api/chat 格式消息（含工具结果回填）
    tool_calls: List[Dict[str, Any]] # 当前轮 LLM 返回的待执行工具调用
    retrieved: List[Dict[str, Any]]  # 检索证据 [{"document_id","title","content","score"}]（供 citations）
    iterations: int                  # 工具循环计数（防死循环，达上限后由 final_answer 收敛）
    guarded: bool                    # 是否被围栏拦截（关键词快路径或 LLM 判定）
    answer: str                      # 最终回答
    warnings: List[str]              # 风险提示列表
