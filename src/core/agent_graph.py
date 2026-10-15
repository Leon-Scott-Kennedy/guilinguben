"""LangGraph 状态机构建"""
from langgraph.graph import StateGraph, END, START
from typing import Literal
from src.core.state import AgentState
from src.core.nodes import (
    node_classifier,
    node_retriever,
    node_generate_rag,
    node_generate_direct,
    node_guardrail,
)


def route_after_classify(state: AgentState) -> Literal["retrieve", "direct_gen", "guardrail"]:
    """条件路由：根据意图决定下一节点"""
    intent = state["intent"]
    if intent == "symptom_query":
        return "retrieve"
    elif intent == "follow_up":
        return "direct_gen"
    else:
        return "guardrail"


class AgentGraph:
    """LangGraph 状态机封装"""

    def __init__(self, retriever, llm, prompt_template=None, strict_mode: bool = True):
        self.retriever = retriever
        self.llm = llm
        self.prompt_template = prompt_template
        self.strict_mode = strict_mode
        self._app = self._build()

    def _build(self):
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("classifier", node_classifier)
        workflow.add_node("retrieve", lambda s: node_retriever(s, self.retriever))
        workflow.add_node("rag_gen", lambda s: node_generate_rag(s, self.llm))
        workflow.add_node("direct_gen", lambda s: node_generate_direct(s, self.llm))
        workflow.add_node("guardrail", lambda s: node_guardrail(s, self.llm))

        # 入口
        workflow.add_edge(START, "classifier")

        # 条件路由
        workflow.add_conditional_edges(
            "classifier",
            route_after_classify,
            {
                "retrieve": "retrieve",
                "direct_gen": "direct_gen",
                "guardrail": "guardrail"
            }
        )

        # 终点边
        workflow.add_edge("retrieve", "rag_gen")
        workflow.add_edge("rag_gen", END)
        workflow.add_edge("direct_gen", END)
        workflow.add_edge("guardrail", END)

        return workflow.compile()

    def invoke(self, state: dict) -> dict:
        """执行状态机"""
        return self._app.invoke(state)


# 保留原函数签名（兼容旧代码）
def build_langgraph_agent(retriever, llm, prompt_template=None, strict_mode=True):
    return AgentGraph(retriever, llm, prompt_template=prompt_template, strict_mode=strict_mode)._app