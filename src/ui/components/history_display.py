"""历史记录展示组件"""
import streamlit as st


def render_history(history: list, max_preview: int = 200):
    """渲染侧边栏历史记录"""
    if not history:
        st.write("暂无历史记录")
        return

    for idx, entry in enumerate(reversed(history)):
        with st.expander(f"查询{len(history) - idx}: {entry['input']}"):
            for r in entry.get('results', []):
                st.write(f"- {r['formula']} (相似度{r['score']:.4f})")
            explanation = entry.get('explanation', '')
            st.write(f"分析：{explanation[:max_preview]}...")