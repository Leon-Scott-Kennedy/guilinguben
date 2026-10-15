"""节点：直接生成（追问路径，冻结检索）"""
from src.core.state import AgentState
from src.config.prompts import DIRECT_GEN_PROMPT_TEMPLATE


def node_generate_direct(state: AgentState, llm):
    history_str = str(state.get("messages", []))
    prompt = DIRECT_GEN_PROMPT_TEMPLATE.format(
        question=state["question"],
        history=history_str
    )
    response = llm.invoke(prompt)
    return {"final_answer": response}