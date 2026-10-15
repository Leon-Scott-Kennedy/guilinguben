"""节点：RAG 生成（症状查询路径）"""
from src.core.state import AgentState
from src.config.prompts import RAG_PROMPT_TEMPLATE


def node_generate_rag(state: AgentState, llm):
    context = "\n".join([
        f"方剂：{doc.metadata['formula']}，原文：{doc.page_content}"
        for doc in state["retrieved_docs"]
    ])

    full_prompt = RAG_PROMPT_TEMPLATE.format(
        question=state["question"],
        context=context,
        history=str(state.get("messages", []))
    )

    response = llm.invoke(full_prompt)
    return {"final_answer": response}