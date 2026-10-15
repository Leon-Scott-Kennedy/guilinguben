"""侧边栏：模式切换 + 历史记录"""
import streamlit as st
from src.ui.components.history_display import render_history


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        # 知识围栏开关
        st.session_state.strict_mode = st.toggle(
            "🔒 知识围栏模式 (仅限桂林古本)",
            value=st.session_state.strict_mode
        )
        st.write(f"当前模式：{'🔒 严格' if st.session_state.strict_mode else '🔓 宽松'}")

        st.header("📋 查询历史")
        if st.button("清空历史"):
            st.session_state.history = []
            st.session_state.message_history = {}
            st.rerun()

        render_history(st.session_state.history)