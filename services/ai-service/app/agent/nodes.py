"""Agent 图节点（B5 版）：B3 围栏/循环/收敛 + 流式事件发射

动态 RAG 开关：检索与否由 LLM 根据问题自主决策（不再依赖预置关键词分类器）；
围栏升级：关键词快路径 + LLM 越界判定慢路径（严格模式与自由模式均执行，
判定失败时 fail-open 放行，保证围栏故障不阻断服务）；
截断收敛：达到循环上限时由 final_answer 节点基于已有证据强制生成回答，不再返回空回答。
B5 流式：节点通过 ContextVar 获取事件发射器（非流式请求时为 None，行为与 B4 完全一致），
推送 status / answer_delta 事件；事件不写入 AgentState（避免 SqliteSaver 序列化问题）。
"""
import contextvars

from app.agent.llm import build_system_prompt, chat_final_answer, chat_guardrail, chat_with_tools
from app.agent.state import AgentState
from app.agent.tools import TOOL_DEFINITIONS, execute_tool_call
from app.memory.history_summarizer import compress_history_context

# 关键词快路径：明显的非中医主题直接拦截（零延迟；未命中再交 LLM 判定）
OUT_OF_SCOPE_KEYWORDS = [
    "写代码", "编程", "python", "java", "股票", "基金", "天气",
    "游戏", "电影", "足球", "篮球",
]

GUARDRAIL_OUT_OF_SCOPE_ANSWER = "本系统仅专注于《桂林古本伤寒杂病论》的学术参考与检索，超出典籍范围的问题请咨询相关专业人士。"

# 流式事件发射器：流式请求时由 main.py 在 invoke 同线程内 set（callable(event_type, payload)），
# 非流式请求保持 None。用 ContextVar 而非写入 AgentState：事件队列无法被 SqliteSaver 序列化，
# 且事件属于传输层关注点，不应污染图状态（B5 设计，见需求书 16.30）。
_stream_emitter: contextvars.ContextVar = contextvars.ContextVar("b5_stream_emitter", default=None)


def emit_event(event_type: str, payload: dict) -> None:
    """向流式通道推送事件；非流式调用时 emitter 为 None，静默忽略"""
    emitter = _stream_emitter.get()
    if emitter:
        try:
            emitter(event_type, payload)
        except Exception as e:
            print(f"[Stream] 事件推送失败（忽略）: {e}")


def node_guardrail(state: AgentState) -> dict:
    """节点：越界围栏拦截，同时初始化对话消息

    两层防线：
    1. 关键词快路径（确定性、零延迟）；
    2. LLM 判定慢路径（关键词未命中时调用，覆盖关键词无法枚举的越界问题）；
    LLM 判定失败时 fail-open 放行并记 warning，避免围栏故障阻断服务。
    """
    question = state["question"].lower()
    if any(k in question for k in OUT_OF_SCOPE_KEYWORDS):
        print(f"[Guardrail] 关键词拦截越界问题：{state['question'][:50]}")
        emit_event("status", {"stage": "guardrail_blocked", "message": "该问题超出系统知识范围。"})
        emit_event("answer_delta", {"text": GUARDRAIL_OUT_OF_SCOPE_ANSWER})
        return {
            "guarded": True,
            "answer": GUARDRAIL_OUT_OF_SCOPE_ANSWER,
            "warnings": ["该问题超出系统知识范围。"],
        }

    warnings = list(state["warnings"])
    # 多轮追问带历史上下文给围栏判定（16.39 修复“刚才说的…再重复一遍”被误拦）
    if chat_guardrail(state["question"], state.get("history_context", "")):
        print(f"[Guardrail] LLM 判定拦截越界问题：{state['question'][:50]}")
        emit_event("status", {"stage": "guardrail_blocked", "message": "该问题超出系统知识范围。"})
        emit_event("answer_delta", {"text": GUARDRAIL_OUT_OF_SCOPE_ANSWER})
        return {
            "guarded": True,
            "answer": GUARDRAIL_OUT_OF_SCOPE_ANSWER,
            "warnings": warnings + ["该问题超出系统知识范围。"],
        }

    user_content = state["question"]
    if state["strict_mode"]:
        # 严格模式：用户消息级强制指令（近因效应强于 system prompt），
        # 防止模型直接复述历史上下文中的旧答案而不调用检索工具
        user_content += "\n（严格模式要求：本次提问必须通过工具检索证据后回答，不得直接复述历史对话中的结论。）"

    messages = [
        # 历史上下文先经摘要化压缩（多轮记忆治理，16.32）：更早轮次→LLM 要点摘要，
        # 最近 1 轮保留原文（指代解析），控制 system prompt token 膨胀
        {"role": "system", "content": build_system_prompt(
            compress_history_context(state["session_id"], state["history_context"]),
            state["strict_mode"],
        )},
        {"role": "user", "content": user_content},
    ]
    print(f"完整的系统提示词是: {messages[0]['content']}...，长度: {len(messages[0]['content'])}")
    return {"guarded": False, "messages": messages, "warnings": warnings}


def node_agent(state: AgentState) -> dict:
    """节点：LLM 决策（调用工具或直接给出最终回答）

    严格模式首轮兜底：模型未调用工具直接回答时，不采纳其回答（正是幻觉条文来源），
    代码强制以原始问题执行一次检索，保证证据闭环后进入第二轮基于证据回答。
    自由模式不兜底，保持 LLM 完全自主（动态 RAG 开关语义）。
    """
    stream_mode = _stream_emitter.get() is not None
    on_token = (lambda delta: emit_event("answer_delta", {"text": delta})) if stream_mode else None
    result = chat_with_tools(state["messages"], TOOL_DEFINITIONS, on_token=on_token)
    assistant_message = {"role": "assistant", "content": result["content"]}

    if result["tool_calls"]:
        # 模型请求调用工具：把含 tool_calls 的 assistant 消息原样回填。
        # 流式场景：本轮为工具决策轮，此前推送的 content 增量（罕见混合场景）不应展示，
        # 推送 status 事件由前端清空已积累的增量文本并转显示检索状态（16.30 兜底设计）
        assistant_message["tool_calls"] = result["tool_calls"]
        tool_names = [tc.get("function", {}).get("name", "unknown") for tc in result["tool_calls"]]
        print(f"[Agent] 第 {state['iterations'] + 1} 轮：模型请求调用 {len(result['tool_calls'])} 个工具")
        emit_event("status", {"stage": "tool_calling", "message": f"正在检索古籍证据（{', '.join(tool_names)}）..."})
        return {
            "messages": state["messages"] + [assistant_message],
            "tool_calls": result["tool_calls"],
        }

    if state["strict_mode"] and state["iterations"] == 0:
        # 严格模式首轮未调用工具：丢弃模型直接回答（可能含幻觉条文），强制注入一次检索。
        # 流式场景：直接回答的增量已推送，随后的 status 事件让前端清空（与 B4 丢弃语义一致）
        print("[Agent] 严格模式首轮模型未调用工具，丢弃直接回答并强制注入检索")
        forced_call = {
            "id": "call_forced_retrieve",
            "function": {"name": "retrieve_guilinguben", "arguments": {"query": state["question"]}},
        }
        emit_event("status", {"stage": "tool_calling", "message": "正在检索古籍证据（retrieve_guilinguben）..."})
        return {
            "messages": state["messages"] + [
                {"role": "assistant", "content": "", "tool_calls": [forced_call]}
            ],
            "tool_calls": [forced_call],
        }

    print(f"[Agent] 模型直接给出回答（未调用工具），长度: {len(result['content'])}")
    return {
        "messages": state["messages"] + [assistant_message],
        "tool_calls": [],
        "answer": result["content"],
    }


def node_tools(state: AgentState, store) -> dict:
    """节点：执行工具调用，结果回填 messages（role=tool），检索证据进 retrieved

    单个工具执行失败不中断整个循环：失败结果以错误文本回填给模型，
    并追加 warning，让模型在下一轮决策时自行调整或说明。
    """
    messages = list(state["messages"])
    new_evidence = []
    warnings = list(state["warnings"])
    for tool_call in state["tool_calls"]:
        tool_name = tool_call.get("function", {}).get("name", "unknown")
        emit_event("status", {"stage": "tool_calling", "message": f"正在执行工具：{tool_name}..."})
        try:
            text, evidence = execute_tool_call(tool_call, store, state["top_k"])
        except Exception as e:
            print(f"[Tools] 工具 {tool_name} 执行失败: {e}")
            text = f"工具 {tool_name} 执行失败：{e}。请基于已有信息继续回答或调整检索方式。"
            evidence = []
            warnings.append(f"工具 {tool_name} 执行失败，回答可能缺少部分证据。")
        messages.append({"role": "tool", "content": text})
        new_evidence.extend(evidence)

    print(f"[Tools] 本轮执行完成，新增证据 {len(new_evidence)} 条，累计 {state['iterations'] + 1} 轮")
    emit_event("status", {"stage": "generating", "message": "已检索到证据，正在生成回答..."})
    return {
        "messages": messages,
        "tool_calls": [],
        "retrieved": state["retrieved"] + new_evidence,
        "iterations": state["iterations"] + 1,
        "warnings": warnings,
    }


def node_final_answer(state: AgentState) -> dict:
    """节点：循环上限收敛——不带工具，基于已有证据强制生成最终回答

    达到 MAX_ITERATIONS 后由路由进入本节点，避免截断时返回空回答；
    生成失败时降级为空串（由 main.py 兜底文案接管）。
    """
    print(f"[Final Answer] 循环收敛：基于 {len(state['retrieved'])} 条证据生成最终回答")
    emit_event("status", {"stage": "generating", "message": "正在生成最终回答..."})
    stream_mode = _stream_emitter.get() is not None
    on_token = (lambda delta: emit_event("answer_delta", {"text": delta})) if stream_mode else None
    answer = chat_final_answer(state["messages"], on_token=on_token)
    return {
        "answer": answer,
        "warnings": state["warnings"] + ["多轮工具调用达到循环上限，已自动收敛为最终回答。"],
    }
