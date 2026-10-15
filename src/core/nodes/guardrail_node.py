"""节点：越界拦截（知识围栏）"""
from src.core.state import AgentState
from src.config.prompts import GUARDRAIL_PROMPT_TEMPLATE


def node_guardrail(state: AgentState, llm):
    if state["strict_mode"]:
        return {
            "final_answer": "⚠️ 本系统仅专注于《桂林古本伤寒杂病论》学术参考，超出典籍范围的问题请咨询执业中医师。"
        }
    else:
        # 宽松模式：LLM 自由回答
        prompt = GUARDRAIL_PROMPT_TEMPLATE.format(
            question=state["question"]
        )
        response = llm.invoke(prompt)
        return {"final_answer": response}