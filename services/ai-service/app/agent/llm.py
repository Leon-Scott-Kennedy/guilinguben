"""本地 LLM 调用封装：Ollama + Qwen，供 Agent 节点使用（B5 支持工具调用与流式）"""
import json
import time

import requests

try:
    from ..config import settings
    from ..metrics import record_llm
except ImportError:  # pragma: no cover
    from app.config import settings
    from app.metrics import record_llm


def build_system_prompt(history_context: str, strict_mode: bool) -> str:
    """构建 Agent 的 system prompt：定义工具使用策略与证据要求

    关键引导：常识/概念性问题直接回答，不调用工具（动态 RAG 开关的模型侧约束）；
    涉及条文、症状、方剂时必须先检索证据再回答。
    """
    strict_part = (
        "严格模式已开启：回答必须基于调用工具检索到的古籍证据，无证据时必须明确说明无法从文献确认。"
        if strict_mode else
        "自由模式：优先使用工具检索证据，常识性问题可直接回答。"
    )
    history_part = ""
    if history_context and history_context.strip():
        history_part = (
            "历史对话上下文（仅供理解对话连续性，其中的回答与引用不构成证据，必须调用工具重新检索验证）：\n"
            f"{history_context}\n"
        )

    return (
        "你是“桂林古本智能辅助诊疗平台”的中医古籍研究助手，基于《桂林古本伤寒杂病论》回答用户问题。\n"
        "工作方式：\n"
        "1. 问题涉及具体症状辨证、条文内容、方剂组成时，必须先调用 retrieve_guilinguben 检索原文证据，再基于证据回答；方剂相关问题可调用 lookup_formula；\n"
        "2. 只有与古籍条文内容无关的一般性问题（如作者生平、成书背景）才可直接回答；\n"
        "3. 严禁仅凭自身知识编造条文编号或引用原文，所有引用必须来自工具返回的证据；\n"
        "4. 即使历史上下文中已出现过相似问题及其回答，也必须调用工具获取当前证据，不得直接复述历史结论；\n"
        "5. 用中文回答，简洁清晰，200 字以内，包含辨证思路与必要的谨慎说明。\n"
        f"{strict_part}\n"
        f"{history_part}"
    )


def normalize_score(raw_score: float) -> float:
    """将 FAISS 原始距离归一化为 0~1 相似度分数"""
    try:
        return round(max(0.0, min(1.0, 1.0 / (1.0 + float(raw_score)))), 4)
    except (TypeError, ValueError):
        return 0.0


def summarize_history(history_text: str) -> str:
    """把多轮对话历史压缩为要点摘要（多轮记忆治理，16.32）

    供 history_summarizer 调用，把旧轮次原文提炼为可复用的要点线索；
    调用失败时返回空串，由调用方降级为原文截断（fail-open，摘要故障不阻断服务）。
    """
    try:
        start = time.time()
        response = requests.post(
            f"{settings.llm_base_url}/api/chat",
            json={
                "model": settings.llm_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是对话历史摘要助手。把多轮问答压缩成要点式摘要，逐条输出（每条一行），"
                            "只保留对后续对话有价值的线索：用户问过的主题、涉及的症状、"
                            "提到的条文编号与方剂名、重要结论（如辨证结果）。"
                            "忽略寒暄与重复内容，总字数 100 字以内；无内容可提炼时输出空行。"
                        ),
                    },
                    {"role": "user", "content": history_text},
                ],
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 200},
            },
            timeout=60,
        )
        response.raise_for_status()
        summary = (response.json().get("message", {}).get("content") or "").strip()
        print(f"[Memory] 历史摘要生成完成，长度: {len(summary)}")
        record_llm("summarize_history", True, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        return summary
    except Exception as e:
        print(f"[Memory] 历史摘要生成失败（降级为原文截断）: {e}")
        record_llm("summarize_history", False, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        return ""


def chat_with_tools(messages: list[dict], tools: list[dict], on_token=None) -> dict:
    """调用 Ollama /api/chat（带工具定义），返回 {"content", "tool_calls"}

    on_token 为 None 时走非流式（B4 原路径，对外行为不变）；
    on_token 为回调时走流式（stream=true）：content 增量逐块回调（B5 打字机推送），
    若最终消息含 tool_calls 则本轮为工具决策轮，调用方需丢弃已推送的增量。

    LLM 不可用时返回降级内容，由调用方决定是否继续。
    """
    try:
        start = time.time()
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "tools": tools,
            "stream": on_token is not None,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "num_predict": 1024,
            },
        }
        if on_token is not None:
            # 流式：逐行解析 Ollama NDJSON 响应，content 增量实时回调，tool_calls 取最后非空值
            print(f"[LLM Chat] 发起流式对话请求，工具数: {len(tools)}")
            response = requests.post(
                f"{settings.llm_base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=120,
            )
            response.raise_for_status()
            content_parts = []
            tool_calls = []
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except ValueError:
                    continue
                message = chunk.get("message") or {}
                delta = message.get("content") or ""
                if delta:
                    content_parts.append(delta)
                    on_token(delta)
                if message.get("tool_calls"):
                    tool_calls = message["tool_calls"]
                if chunk.get("done"):
                    break
            if tool_calls:
                print(f"[LLM Chat] 模型请求调用工具: {[tc['function']['name'] for tc in tool_calls]}")
            record_llm("chat_with_tools", True, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
            return {
                "content": "".join(content_parts).strip(),
                "tool_calls": tool_calls,
            }

        print(f"[LLM Chat] 发起对话请求，工具数: {len(tools)}")
        response = requests.post(
            f"{settings.llm_base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        message = response.json().get("message", {})
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            print(f"[LLM Chat] 模型请求调用工具: {[tc['function']['name'] for tc in tool_calls]}")
        record_llm("chat_with_tools", True, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        return {
            "content": (message.get("content") or "").strip(),
            "tool_calls": tool_calls,
        }
    except Exception as e:
        print(f"LLM Chat Error: {e}")
        record_llm("chat_with_tools", False, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）：降级返回也算调用失败
        return {
            "content": "当前本地模型服务不可用，请稍后重试或检查 Ollama 服务状态。",
            "tool_calls": [],
        }


def chat_guardrail(question: str, history_hint: str = "") -> bool:
    """LLM 围栏判定：问题是否超出《桂林古本伤寒杂病论》中医古籍领域（True=越界）

    多轮追问（如“刚才说的桂枝汤组成再重复一遍”）脱离上下文无法判断领域，
    传入 history_hint（历史上下文片段）辅助判定（16.39 评测发现追问误拦后修复）。
    调用失败时返回 False（fail-open：围栏故障不阻断服务，宁可放行也不误伤正常提问）。
    """
    hint_text = (
        f"\n这是多轮对话中的追问。历史对话内容片段：{history_hint[-300:]}"
        "\n若该追问指向的历史话题属于中医范畴，应判 YES。"
    ) if history_hint else ""
    try:
        start = time.time()
        response = requests.post(
            f"{settings.llm_base_url}/api/chat",
            json={
                "model": settings.llm_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是系统内容安全围栏。判断用户问题是否属于中医古籍《桂林古本伤寒杂病论》"
                            "的研究范畴。属于该范畴的问题包括：症状辨证（如发热、恶寒、头痛、汗出等）、"
                            "条文内容查询、方剂组成与适用症状、药物、中医理论与辨证思路、古籍作者与成书背景、"
                            "中医常识性概念（如什么是伤寒论、张仲景是谁、阴阳的含义等）。"
                            "只输出一个词：YES（属于该范畴）或 NO（不属于）。\n"
                            "示例：\n"
                            "Q: 发热恶寒是什么证 A: YES\n"
                            "Q: 桂枝汤的组成 A: YES\n"
                            "Q: 什么是伤寒论 A: YES\n"
                            "Q: 张仲景是谁 A: YES\n"
                            "Q: 中医的阴阳是什么意思 A: YES\n"
                            "Q: 帮我写一首诗 A: NO\n"
                            "Q: 什么是微积分 A: NO\n"
                            "Q: 今天天气怎么样 A: NO"
                            + hint_text
                        ),
                    },
                    {"role": "user", "content": question},
                ],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 8},
            },
            timeout=60,
        )
        response.raise_for_status()
        content = (response.json().get("message", {}).get("content") or "").strip().upper()
        out_of_scope = content.startswith("NO")
        print(f"[Guardrail] LLM 判定：{question[:30]} -> 越界={out_of_scope}")
        record_llm("chat_guardrail", True, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        return out_of_scope
    except Exception as e:
        print(f"[Guardrail] LLM 判定失败（fail-open 放行）: {e}")
        record_llm("chat_guardrail", False, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        return False


def chat_final_answer(messages: list[dict], on_token=None) -> str:
    """循环上限收敛：不带工具，基于已有对话与工具结果强制生成最终回答

    达到 MAX_ITERATIONS 后调用，防止模型在截断时留下空回答；
    on_token 为 None 时非流式（B4 原路径），否则流式推送 content 增量（B5）；
    调用失败时返回空串，由调用方走降级文案。
    """
    try:
        start = time.time()
        payload = {
            "model": settings.llm_model,
            "messages": messages + [
                {
                    "role": "user",
                    "content": "（系统指令）工具调用阶段已结束，请立即基于上述已检索到的证据给出最终回答，不要再请求任何工具。",
                }
            ],
            "stream": on_token is not None,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "num_predict": 1024,
            },
        }
        if on_token is not None:
            response = requests.post(
                f"{settings.llm_base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=120,
            )
            response.raise_for_status()
            content_parts = []
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except ValueError:
                    continue
                delta = (chunk.get("message") or {}).get("content") or ""
                if delta:
                    content_parts.append(delta)
                    on_token(delta)
                if chunk.get("done"):
                    break
            record_llm("chat_final_answer", True, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
            return "".join(content_parts).strip()

        response = requests.post(
            f"{settings.llm_base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        record_llm("chat_final_answer", True, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        return (response.json().get("message", {}).get("content") or "").strip()
    except Exception as e:
        print(f"[Final Answer] 收敛生成失败: {e}")
        record_llm("chat_final_answer", False, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        return ""


def local_llm_response(prompt: str) -> str:
    """调用本地 Ollama 模型生成回答（同步阻塞式）"""
    try:
        start = time.time()
        # Print the prompt to the console for debugging/verification
        print(f"\n[LLM Prompt]\n{prompt}\n[/LLM Prompt]\n")

        response = requests.post(
            f"{settings.llm_base_url}/api/generate",
            json={
                "model": settings.llm_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "num_predict": 200,  # 恢复合理的生成长度，避免截断
                },
            },
            timeout=60,  # 增加超时时间以容纳更长的生成过程
        )
        response.raise_for_status()
        payload = response.json()
        record_llm("local_llm_response", True, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        return payload.get("response", "").strip() or "当前无法由本地模型生成可用回答。"
    except Exception as e:
        # Log the actual error for debugging purposes in a real scenario
        print(f"LLM Error: {e}")
        record_llm("local_llm_response", False, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        # Return a fallback message with the evidence already retrieved
        return "当前本地模型服务不可用，已返回基于检索证据的简要说明。"


def generate_answer(question: str, evidence: list[str], history_context: str = "") -> str:
    """基于检索证据生成回答；无证据时降级为通用知识问答并附带免责声明"""
    print(f"[DEBUG] generate_answer called - history_context length: {len(history_context)}")

    history_part = ""
    if history_context and history_context.strip():
        history_part = f"历史对话上下文：\n{history_context}\n\n"
        print("[DEBUG] History context injected into prompt")
    else:
        print("[DEBUG] No history context to inject")

    if not evidence:
        prompt = (
            f"{history_part}问题：{question}\n\n"
            "请作为中医古籍研究助手回答问题。注意：未在提供的文献中检索到直接相关证据，"
            "以下回答仅基于通用医学知识，请务必结合专业医师建议并查阅原始文献。"
            "请保持回答简洁，控制在 200 字以内。"
        )
    else:
        context = "\n\n".join(f"- {item}" for item in evidence[:3])
        prompt = (
            "请你作为中医古籍研究助手，基于以下古籍条文证据回答问题。\n"
            "要求：\n"
            "1. 回答必须只基于提供的证据，不得编造来源。\n"
            "2. 结构清晰，包含辨证思路、治法要点和必要的谨慎说明。\n"
            "3. 语言精炼，总字数控制在 200 字以内。\n\n"
            f"{history_part}问题：{question}\n\n证据：\n{context}\n\n"
            "请用中文回答："
        )

    print(f"[DEBUG] Final prompt length: {len(prompt)}")
    return local_llm_response(prompt)
