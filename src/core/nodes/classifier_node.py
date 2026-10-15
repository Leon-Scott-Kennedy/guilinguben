"""节点：意图分类"""
from src.core.state import AgentState
from src.core.intent_classifier import classify_intent


def node_classifier(state: AgentState):
    question = state["question"]
    history = state.get("messages", [])
    intent = classify_intent(question, history)
    print(f"[Router] 识别意图：{intent}")
    return {"intent": intent}