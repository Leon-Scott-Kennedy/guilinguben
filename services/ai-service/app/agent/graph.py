"""LangGraph Agent 图构建与封装（B4 版：会话检查点 SqliteSaver）"""
import sqlite3
from typing import Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import node_agent, node_final_answer, node_guardrail, node_tools
from app.agent.state import AgentState
from app.config import BASE_DIR

# 工具循环上限：防止模型反复调用工具导致死循环
MAX_ITERATIONS = 3

# 会话检查点 SQLite 文件：按 thread_id（=session_id）持久化各会话的图内执行状态。
# 存储介质选型背景见需求书 16.24：MemorySaver（进程内存，重启丢失）/
# SqliteSaver（本地文件，与 Java 端业务库解耦，符合“数据库操作留在 Java 端”约束）/
# PostgresSaver（Python 直连 PostgreSQL，与架构约束冲突，留作多实例部署演进项）
CHECKPOINT_DB_PATH = BASE_DIR / "data" / "checkpoints.sqlite"


def route_after_guardrail(state: AgentState) -> Literal["agent", "end"]:
    """围栏路由：越界直接结束，否则进入 Agent 决策循环"""
    return "end" if state["guarded"] else "agent"


def route_after_agent(state: AgentState) -> Literal["tools", "end"]:
    """Agent 决策路由：有工具调用则执行工具，否则结束"""
    return "tools" if state["tool_calls"] else "end"


def route_after_tools(state: AgentState) -> Literal["agent", "final_answer"]:
    """工具执行后路由：达到循环上限则进入收敛节点，否则回到 Agent 继续决策"""
    if state["iterations"] >= MAX_ITERATIONS:
        print(f"[Graph] 达到工具循环上限 {MAX_ITERATIONS} 轮，进入 final_answer 收敛")
        return "final_answer"
    return "agent"


def build_agent_graph(store):
    """构建 Agent 状态机：guardrail -> agent <-> tools -> final_answer

    guardrail 为双层围栏（关键词快路径 + LLM 越界判定，fail-open）；
    agent 节点由 LLM 自主决定调用检索/方剂工具或直接回答（动态 RAG 开关）；
    tools 节点执行工具并回填结果，循环直至 LLM 给出最终回答；
    达到循环上限时由 final_answer 基于已有证据强制收敛回答，避免空回答。

    图挂载 SqliteSaver 会话检查点（thread_id=session_id），跨请求持久化图内状态；
    对外行为不变（方案甲：history_context 仍由 Java 端注入，图内消息链不接管多轮上下文）。
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("guardrail", node_guardrail)
    workflow.add_node("agent", node_agent)
    workflow.add_node("tools", lambda s: node_tools(s, store))
    workflow.add_node("final_answer", node_final_answer)

    workflow.add_edge(START, "guardrail")
    workflow.add_conditional_edges(
        "guardrail",
        route_after_guardrail,
        {"agent": "agent", "end": END},
    )
    workflow.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "end": END},
    )
    workflow.add_conditional_edges(
        "tools",
        route_after_tools,
        {"agent": "agent", "final_answer": "final_answer"},
    )
    workflow.add_edge("final_answer", END)

    # 挂载 SqliteSaver 检查点：每次 invoke 按 thread_id 落盘图内状态，
    # 实现跨请求持久化与重启恢复（执行轨迹可审计，为原生消息链多轮铺好存储层）
    # check_same_thread=False 是安全的：SqliteSaver 内部使用 threading.Lock 保证线程安全
    conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return workflow.compile(checkpointer=checkpointer)
