"""检索结果展示组件"""
from typing import List


def format_retrieved_docs(docs) -> List[dict]:
    """
    将 LangGraph 返回的 Document 列表格式化为 UI 展示格式。
    注：LangGraph 检索器不返回 score，这里用 1.0 占位。
    """
    results = []
    for doc in docs:
        results.append({
            'formula': doc.metadata['formula'],
            'symptom': doc.page_content,
            'score': 1.0
        })
    return results


def render_retrieved_docs(docs, max_display: int = 3):
    """在 Streamlit 中渲染检索结果"""
    import streamlit as st
    if not docs:
        st.info("💡 本次回答未检索古籍条文，基于上下文生成。")
        return

    st.subheader("📚 参考条文 (Top-3)")
    for i, doc in enumerate(docs[:max_display], 1):
        st.markdown(f"**{i}. {doc.metadata['formula']}**")
        st.caption(f"原文症状：{doc.page_content}")
        st.divider()