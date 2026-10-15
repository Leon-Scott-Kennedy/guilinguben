"""Streamlit 主页面"""
import streamlit as st
import uuid
from langchain_community.llms import Ollama

from src.config.settings import settings
from src.config.prompts import RAG_PROMPT_TEMPLATE
from src.data.loader import DataLoader
from src.data.vector_store import VectorStoreManager
from src.models.embedding import EmbeddingManager
from src.core.agent_graph import AgentGraph
from src.memory.session_history import get_session_history, generate_with_graph
from src.ui.components.result_display import render_retrieved_docs, format_retrieved_docs
from src.ui.sidebar import render_sidebar


# ========== Streamlit 缓存加载 ==========
@st.cache_resource
def load_data():
    """加载语料数据"""
    loader = DataLoader(settings.data_path)
    texts, labels = loader.load()
    return texts, labels


@st.cache_resource
def build_retriever(_texts, _labels):
    """构建 FAISS 检索器"""
    embedding_manager = EmbeddingManager(settings.embedding_model_path)
    vector_store = VectorStoreManager(embedding_manager, top_k=settings.top_k)
    vector_store.build_index(_texts, _labels)
    return vector_store


@st.cache_resource
def build_agent(_retriever, _llm):
    """构建 LangGraph Agent"""
    return AgentGraph(
        retriever=_retriever.get_retriever(),
        llm=_llm,
        strict_mode=True
    )


# ========== 初始化 ==========
def run_ui():
    st.set_page_config(page_title="桂林古本辅助诊疗", layout="centered")

    # 加载数据
    texts, labels = load_data()
    vector_store = build_retriever(texts, labels)

    # 初始化 LLM
    llm = Ollama(model=settings.llm_model_name, temperature=settings.llm_temperature)

    # 构建 Agent
    agent = build_agent(vector_store, llm)

    # 初始化 session_state
    if "history" not in st.session_state:
        st.session_state.history = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "strict_mode" not in st.session_state:
        st.session_state.strict_mode = True

    # ---------- UI ----------
    st.title("📜 桂林古本 · 方剂语义检索 (Agent 版)")
    st.markdown("输入症状描述，系统将根据《桂林古本》条文推荐最匹配的方剂。")

    user_input = st.text_input("请输入症状（简体中文）:", placeholder="例如：发热，恶风，汗出")

    if st.button("检索推荐"):
        if not user_input.strip():
            st.warning("请先输入症状！")
        else:
            # 预处理
            from src.data.preprocessor import clean_text, to_simplified
            cleaned_input = to_simplified(clean_text(user_input))

            # 调用 LangGraph
            with st.spinner("正在分析意图并生成辩证..."):
                final_answer, retrieved_docs = generate_with_graph(
                    cleaned_input,
                    st.session_state.session_id,
                    st.session_state.strict_mode,
                    agent._app
                )

                # 手动追加对话历史
                history = get_session_history(st.session_state.session_id)
                history.add_user_message(user_input)
                history.add_ai_message(final_answer)

            # 展示检索结果
            render_retrieved_docs(retrieved_docs)

            # 展示 AI 分析
            st.subheader("🧠 AI 辨证分析")
            st.write(final_answer)

            # 保存历史记录
            st.session_state.history.append({
                "input": user_input,
                "results": format_retrieved_docs(retrieved_docs) if retrieved_docs else [],
                "explanation": final_answer
            })

    # 侧边栏
    render_sidebar()


if __name__ == "__main__":
    main()