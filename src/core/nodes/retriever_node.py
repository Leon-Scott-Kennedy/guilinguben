"""节点：FAISS 检索"""
from src.core.state import AgentState


def node_retriever(state: AgentState, retriever):
    docs = retriever.invoke(state["question"])
    return {"retrieved_docs": docs}