from pathlib import Path
from uuid import uuid4

import json
import queue
import re
import threading
import time

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

try:
    from .agent.graph import build_agent_graph
    from .agent.llm import local_llm_response
    from .agent.nodes import _stream_emitter
    from .agent.state import AgentState
    from .config import settings
    from .metrics import metrics_snapshot, record_interface
    from .schemas import AnalyzeRequest, AnalyzeResponse, Citation, ExplainTextRequest, ExplainTextResponse
    from .retrieval.chroma_store import ChromaVectorStore
    from .retrieval.embedding import LocalEmbeddingProvider
    from .retrieval.faiss_store import FaissVectorStore
    from .retrieval.milvus_store import MilvusVectorStore
    from .retrieval.pdf_loader import PdfDocumentLoader
    from .retrieval.ports import VectorStore
except ImportError:  # pragma: no cover
    from app.agent.graph import build_agent_graph
    from app.agent.llm import local_llm_response
    from app.agent.nodes import _stream_emitter
    from app.agent.state import AgentState
    from app.config import settings
    from app.metrics import metrics_snapshot, record_interface
    from app.schemas import AnalyzeRequest, AnalyzeResponse, Citation, ExplainTextRequest, ExplainTextResponse
    from app.retrieval.chroma_store import ChromaVectorStore
    from app.retrieval.embedding import LocalEmbeddingProvider
    from app.retrieval.faiss_store import FaissVectorStore
    from app.retrieval.milvus_store import MilvusVectorStore
    from app.retrieval.pdf_loader import PdfDocumentLoader
    from app.retrieval.ports import VectorStore

def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-Api-Key")) -> None:
    """内部 API Key 校验（预留，D 轮 16.40 取舍三）：settings.ai_service_api_key 为空时跳过（默认关闭）；
    生产配置非空后，所有接口必须携带 X-Api-Key 头才能访问（与 Java ai-service.api-key 配对启用）。"""
    if settings.ai_service_api_key and x_api_key != settings.ai_service_api_key:
        raise HTTPException(status_code=401, detail="invalid api key")


app = FastAPI(title=settings.app_name, version="0.1.0", dependencies=[Depends(verify_api_key)])

# 索引目录
INDEX_DIR = Path(__file__).resolve().parents[3] / "data" / "faiss_index"

# 条文编号模式（如【6.2】/[4.9]）：自由模式弱兜底检测用（16.32）
_REF_PATTERN = re.compile(r"[【\[]\s*\d+\.\d+\s*[】\]]")


class RetrievalService:
    """单例检索服务：管理 Embedding 模型和向量库的生命周期"""
    
    _instance = None
    _store: VectorStore | None = None
    _provider: LocalEmbeddingProvider | None = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        """初始化检索服务（只执行一次）"""
        if self._initialized:
            return
        
        print("[RetrievalService] 正在初始化...")
        
        # 1. 加载 Embedding 模型（单例）
        print("[RetrievalService] 加载 Embedding 模型...")
        import os
        from pathlib import Path as P
        model_path = settings.embedding_model_path
        if not P(model_path).is_absolute():
            from app.config import BASE_DIR
            model_path = str(BASE_DIR / model_path)
            
        self._provider = LocalEmbeddingProvider(model_path=model_path)
        embeddings = self._provider.get_embeddings()
        print("[RetrievalService] ✓ Embedding 模型加载完成")
        
        # 2. 初始化向量库（vector_backend 开关：faiss 本地 MVP / milvus 16.33 / chroma 16.37）
        if settings.vector_backend == "milvus":
            self._store = MilvusVectorStore(
                embeddings, uri=settings.milvus_uri, collection_name=settings.milvus_collection_name
            )
            try:
                exists = self._store.collection_exists()
            except Exception as e:
                raise RuntimeError(
                    f"无法连接 Milvus（{settings.milvus_uri}），请先启动 milvus 容器或切换 vector_backend=faiss: {e}"
                )
            if exists:
                print(f"[RetrievalService] Milvus collection 已存在: {settings.milvus_collection_name}（检索时惰性加载）")
            else:
                print("[RetrievalService] Milvus collection 不存在，正在从 PDF 构建...")
                loader = PdfDocumentLoader(settings.source_pdf_path)
                documents = loader.load()
                print(f"[RetrievalService] ✓ 解析完成，生成 {len(documents)} 个文本片段")
                self._store.build_index(documents)
                print("[RetrievalService] ✓ Milvus 灌数与索引构建完成")
        elif settings.vector_backend == "chroma":
            self._store = ChromaVectorStore(
                embeddings,
                persist_dir=settings.chroma_persist_dir,
                collection_name=settings.chroma_collection_name,
            )
            if self._store.collection_exists():
                print(f"[RetrievalService] Chroma collection 已存在: {settings.chroma_collection_name}（检索时惰性加载）")
            else:
                print("[RetrievalService] Chroma collection 不存在，正在从 PDF 构建...")
                loader = PdfDocumentLoader(settings.source_pdf_path)
                documents = loader.load()
                print(f"[RetrievalService] ✓ 解析完成，生成 {len(documents)} 个文本片段")
                self._store.build_index(documents)
                print("[RetrievalService] ✓ Chroma 灌数与索引构建完成")
        else:
            self._store = FaissVectorStore(embeddings, index_path=INDEX_DIR)

        # 3. FAISS 分支：尝试加载预构建的索引（Milvus 分支在上方已完成）
        if settings.vector_backend == "faiss":
            if self._store.index_exists():
                print(f"[RetrievalService] 发现预构建索引，正在加载: {INDEX_DIR}")
                self._store.load_index()
                print("[RetrievalService] ✓ 索引加载完成（秒级启动）")
            else:
                print(f"[RetrievalService] 未找到预构建索引，正在从 PDF 构建...")
                loader = PdfDocumentLoader(settings.source_pdf_path)
                documents = loader.load()
                print(f"[RetrievalService] ✓ 解析完成，生成 {len(documents)} 个文本片段")

                print("[RetrievalService] 正在构建 FAISS 索引...")
                self._store.build_index(documents)
                print("[RetrievalService] ✓ FAISS 索引构建完成")

                INDEX_DIR.mkdir(parents=True, exist_ok=True)
                self._store.save_index()
                print(f"[RetrievalService] ✓ 索引已保存到: {INDEX_DIR}")
        
        self._initialized = True
        print("[RetrievalService] ✓ 初始化完成")
    
    def get_store(self) -> "VectorStore":
        """获取向量库实例"""
        if not self._initialized:
            self.initialize()
        return self._store


# 全局检索服务实例
retrieval_service = RetrievalService()

# Agent 图缓存：向量库为单例，图只需构建一次（后续请求直接 invoke 复用）
_agent_graph = None


def _get_agent_graph(store):
    """惰性构建并缓存 Agent 图，避免每次请求重复编译"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph(store)
        print("[Agent] LangGraph Agent 图构建完成")
    return _agent_graph


@app.on_event("startup")
async def startup_event():
    """服务启动时预加载索引"""
    retrieval_service.initialize()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.get("/metrics")
def metrics() -> dict:
    """调用指标快照（⑥16.41）：接口层请求计数/成功率/平均耗时 + LLM 层模型调用计数（进程内，重启清零）"""
    return metrics_snapshot()


def _build_initial_state(request: AnalyzeRequest) -> AgentState:
    """构建图初始状态（流式/非流式共用）"""
    return {
        "question": request.question,
        "session_id": request.session_id,
        "history_context": request.history_context,
        "strict_mode": request.strict_mode,
        "top_k": request.top_k,
        "messages": [],
        "tool_calls": [],
        "retrieved": [],
        "iterations": 0,
        "guarded": False,
        "answer": "",
        "warnings": [],
    }


def _execute_agent(request: AnalyzeRequest) -> dict:
    """执行 Agent 图并返回原始图状态结果（流式/非流式共用）"""
    store = retrieval_service.get_store()
    graph = _get_agent_graph(store)
    import time
    graph_start = time.time()
    # thread_id 映射 session_id：同会话的图内状态跨请求累计持久化（重启不丢，见 16.24）
    result = graph.invoke(_build_initial_state(request), config={"configurable": {"thread_id": request.session_id}})
    graph_elapsed = time.time() - graph_start
    print(f"[Agent] 图执行完成 - 证据数: {len(result['retrieved'])}, 工具轮数: {result['iterations']}, 回答长度: {len(result['answer'])}, 图耗时: {graph_elapsed:.2f}s")
    return result


def _build_final_response(result: dict) -> AnalyzeResponse:
    """图结果后处理：空回答降级、intent 判定、citations/warnings 组装（流式/非流式共用）"""
    answer = result["answer"]
    warnings = list(result["warnings"])
    if not answer.strip():
        # final_answer 收敛失败（LLM 不可用等极端情况）：降级提示，避免返回空回答
        answer = "本轮分析因工具调用次数达到上限而提前结束，未能生成完整回答，请简化问题后重试。"
        warnings.append("工具调用达到循环上限，回答可能不完整。")

    citations = [Citation(**r) for r in result["retrieved"]]
    if result["guarded"]:
        intent = "out_of_scope"
    elif result["retrieved"] and all(
        str(r.get("document_id", "")).startswith("formula_db:") for r in result["retrieved"]
    ):
        # 证据全部来自方剂库（模型仅调 lookup_formula，如“麻黄汤的组成”）：
        # 与检索证据同构计入 citations 后，intent 不再误标 no_match（方剂结构化引用，16.31）
        intent = "formula_query"
        warnings.append("本结果基于桂林古本方剂库数据，不构成临床诊断或处方建议。")
    elif result["retrieved"]:
        intent = "symptom_query"
        warnings.append("本结果仅基于本地 PDF 检索证据，不构成临床诊断或处方建议。")
    else:
        # 未走检索路径（LLM 直接回答的常识/概念性问题）：保持契约值域，标记为未匹配证据
        intent = "no_match"
        warnings.append("本回答未基于文献检索证据，仅供参考，请结合专业医师建议。")
        # 自由模式弱兜底（16.32）：回答出现条文编号（如【6.2】）但本轮无工具证据，
        # 说明模型可能凭记忆引用未验证条文，追加警示提醒用户（严格模式另有限制，不再叠加）
        if not result.get("strict_mode", True) and _REF_PATTERN.search(answer):
            warnings.append("检测到回答引用了条文编号，但本轮未经过文献检索验证，请谨慎参考，必要时开启严格模式复核。")

    print(f"[全链路] Python 响应摘要: intent={intent}, citations数={len(citations)}, warnings数={len(warnings)}, 回答前80字={answer[:80]}")

    return AnalyzeResponse(
        request_id=str(uuid4()),
        answer=answer,
        intent=intent,
        citations=citations,
        warnings=warnings,
        status="COMPLETED",
    )


@app.post("/api/agent/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """通过 LangGraph Agent 图执行分析（B5 版：非流式，对外契约不变）

    执行路径：guardrail（关键词快路径 + LLM 越界判定）-> agent <-> tools -> final_answer 收敛 -> END；
    图按 thread_id=session_id 挂载 SqliteSaver 检查点，跨请求持久化图内执行状态（方案甲：
    history_context 仍由 Java 端注入，图内消息链暂不接管多轮上下文，对外行为零变化）。
    流式输出请使用 /api/agent/analyze/stream（B5，同一图与后处理逻辑）。
    """
    print(f"[DEBUG] Received request - session_id: {request.session_id}, question: {request.question}")
    print(f"[DEBUG] strict_mode: {request.strict_mode}, top_k: {request.top_k}")
    print(f"[DEBUG] Received history_context length: {len(request.history_context)}")
    if request.history_context:
        print(f"[DEBUG] Received history_context preview: {request.history_context[:100]}")

    start = time.time()
    try:
        result = _execute_agent(request)
        response = _build_final_response(result)
        record_interface("analyze", True, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        return response
    except Exception:
        record_interface("analyze", False, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        raise


@app.post("/api/agent/analyze/stream")
def analyze_stream(request: AnalyzeRequest) -> StreamingResponse:
    """SSE 流式分析（B5）：与 /api/agent/analyze 同一 Agent 图与后处理逻辑，输出改为事件流

    事件协议（均带自增 id，供消费端去重/断点续传，16.30 Layer 1）：
    - status:      阶段状态（payload.stage/message：guardrail_blocked/tool_calling/generating）
    - answer_delta:回答 token 增量（payload.text）
    - done:        最终完整结果（AnalyzeResponse 全字段，供落库与渲染引用证据卡）
    - error:       执行异常（payload.message/recoverable）

    实现：图在独立线程同步执行（节点经 ContextVar 读取发射器，事件不写入 AgentState），
    事件经有界队列交给 StreamingResponse 生成器；队列满时丢弃事件（消费端断连时防内存膨胀）。
    """
    print(f"[Stream] 收到流式请求 - session_id: {request.session_id}, question: {request.question[:50]}")

    start = time.time()
    event_queue: queue.Queue = queue.Queue(maxsize=1000)
    closed = threading.Event()
    dropped = {"count": 0}

    def emitter(event_type: str, payload: dict) -> None:
        """节点事件发射器：非阻塞入队；消费端断连时队列会满，丢弃并计数（防内存膨胀）"""
        try:
            event_queue.put_nowait((event_type, payload))
        except queue.Full:
            dropped["count"] += 1

    def run_graph() -> None:
        """图执行线程：ContextVar 在此线程内 set，invoke 同步执行保证节点同线程读取"""
        try:
            _stream_emitter.set(emitter)
            result = _execute_agent(request)
            emitter("done", _build_final_response(result).model_dump())
            record_interface("analyze_stream", True, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        except Exception as e:
            print(f"[Stream] 图执行异常: {e}")
            emitter("error", {"message": f"流式分析执行失败: {e}", "recoverable": False})
            record_interface("analyze_stream", False, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        finally:
            if dropped["count"]:
                print(f"[Stream] 本次请求丢弃事件 {dropped['count']} 条（消费端断连或处理过慢）")
            closed.set()

    threading.Thread(target=run_graph, daemon=True).start()

    def sse_generator():
        event_id = 0
        while True:
            try:
                item = event_queue.get(timeout=0.2)
            except queue.Empty:
                if closed.is_set():
                    break
                continue
            event_id += 1
            event_type, payload = item
            yield f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/agent/explain", response_model=ExplainTextResponse)
def explain_text(request: ExplainTextRequest) -> ExplainTextResponse:
    """对选中的古籍文本进行白话文解释或辨证分析"""
    selected_text = request.question  # 复用 question 字段传递选中文本
    
    prompt = (
        f"请作为中医古籍研究助手，对以下《桂林古本伤寒杂病论》中的原文片段进行解释：\n\n"
        f"原文：{selected_text}\n\n"
        "要求：\n"
        "1. 提供通俗易懂的白话文翻译。\n"
        "2. 简要说明其在中医辨证中的含义或临床价值。\n"
        "3. 保持专业且简洁，字数控制在 200 字以内。"
    )
    
    explanation = ""
    start = time.time()
    try:
        explanation = local_llm_response(prompt)
        record_interface("explain", True, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
    except Exception:
        record_interface("explain", False, (time.time() - start) * 1000)  # 指标埋点（⑥16.41）
        raise

    return ExplainTextResponse(
        answer=explanation
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.server_host, port=settings.server_port, reload=True)
