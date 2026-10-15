"""Agent 状态定义"""
from typing import List, Dict, Any, Literal, TypedDict


class AgentState(TypedDict):
    """LangGraph 状态机的核心状态结构"""
    messages: List[Dict[str, str]]          # 对话历史 [{"role": "human/ai", "content": "..."}]
    question: str                           # 当前用户问题
    intent: Literal["symptom_query", "follow_up", "out_of_scope"]  # 意图标签
    retrieved_docs: List[Any]               # FAISS 检索结果（Document 列表）
    strict_mode: bool                       # 知识围栏开关
    final_answer: str                       # 最终输出