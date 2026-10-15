"""会话历史管理：Streamlit session_state 与 ChatMessageHistory 桥接"""
import streamlit as st
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from src.core.agent_graph import AgentGraph


def get_session_history(session_id: str) -> ChatMessageHistory:
    """从 Streamlit session_state 获取或创建 ChatMessageHistory"""
    if "message_history" not in st.session_state:
        st.session_state.message_history = {}
    if session_id not in st.session_state.message_history:
        st.session_state.message_history[session_id] = ChatMessageHistory()
    return st.session_state.message_history[session_id]


def generate_with_graph(cleaned_input: str, session_id: str, strict_mode: bool, agent_app):
    """
    调用 LangGraph 状态机生成回答。
    返回 (final_answer, retrieved_docs)
    """
    # 1. 获取历史
    history = get_session_history(session_id).messages
    hist_list = [
        {"role": "human" if isinstance(m, HumanMessage) else "ai", "content": m.content}
        for m in history
    ]

    # 2. 构造初始状态
    initial_state = {
        "messages": hist_list,
        "question": cleaned_input,
        "intent": "",
        "retrieved_docs": [],
        "strict_mode": strict_mode,
        "final_answer": ""
    }

    # 3. 执行状态机
    final_state = agent_app.invoke(initial_state)
    return final_state["final_answer"], final_state.get("retrieved_docs", [])