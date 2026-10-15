"""Agent 工具集：向量检索 + 方剂库查询（C 轮版）

工具定义遵循 Ollama /api/chat 的 function calling 格式；
execute_tool_call 为统一分发入口，供图节点调用。
"""
import json
from functools import lru_cache
from typing import Any, Dict, List, Tuple

from zhconv import convert

try:
    from ..config import BASE_DIR
    from .llm import normalize_score
except ImportError:  # pragma: no cover
    from app.config import BASE_DIR
    from app.agent.llm import normalize_score

# 方剂库数据文件：后续将按"一个条文一条数据"重新切分 PDF 并向量化后替换
FORMULA_DB_PATH = BASE_DIR / "data" / "桂林古本方剂提取结果.json"

# Ollama tools 定义（function calling 格式）
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_guilinguben",
            "description": "检索《桂林古本伤寒杂病论》原文，返回与查询相关的条文证据及页码，供回答引用",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词，如症状描述或条文主题"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_formula",
            "description": "查询桂林古本方剂库，按方剂名返回书页页码、药物组成与注意事项（同名方剂多次出现时返回多条）",
            "parameters": {
                "type": "object",
                "properties": {
                    "formula_name": {"type": "string", "description": "方剂名称，如麻黄汤、桂枝汤"},
                },
                "required": ["formula_name"],
            },
        },
    },
]


@lru_cache(maxsize=1)
def load_formula_db() -> List[Dict[str, str]]:
    """加载方剂提取结果 JSON（进程内缓存，只读一次）"""
    with open(FORMULA_DB_PATH, encoding="utf-8") as f:
        return json.load(f)


# 繁→简归一化：方剂库 formula 字段为繁体（如“麻黃湯”），模型生成的方剂名多为简体（“麻黄汤”），
# 直接子串匹配会漏检，需先归一化为简体再匹配。原先用硬编码常见字映射表，
# 现改用 zhconv 全量转换（zh-cn 词典覆盖完整，不依赖手工维护的字表）。
@lru_cache(maxsize=8192)
def _to_simplified(text: str) -> str:
    """繁→简归一化（zhconv 全量转换，结果缓存），用于跨繁简匹配"""
    return convert(text, "zh-cn")


def lookup_formula(formula_name: str) -> Tuple[str, List[Dict[str, Any]]]:
    """按方剂名匹配方剂库（繁简兼容），返回（格式化结果文本, 结构化证据列表）

    方剂库为 C 轮 4 字段（ref 条文编号 / book_page 书页 / formula 方剂名 /
    composition 药物组成 / notes 注意事项-煎服法）；同名方剂出现几次就有几条数据。
    结构化证据与检索证据同构（document_id/title/content/score），可直接计入 citations；
    document_id 以 "formula_db:" 前缀标识方剂库来源，供 intent 归类区分。
    """
    db = load_formula_db()
    query = _to_simplified(formula_name.strip())
    matches = [item for item in db if query and query in _to_simplified(item.get("formula", ""))]
    if not matches:
        return f"方剂库中未找到与「{formula_name}」匹配的方剂。", []
    # 精确同名优先（查“麻黄汤”时“麻黃湯”在“射干麻黃湯”等含子串的变方之前）
    matches.sort(key=lambda item: 0 if _to_simplified(item.get("formula", "")) == query else 1)
    lines = []
    evidence = []
    for item in matches[:10]:
        formula = item.get("formula", "?")
        ref = item.get("ref", "?")
        book_page = item.get("book_page", "?")
        composition = item.get("composition", "")
        notes = item.get("notes", "")
        body = [f"条文 {ref}，书页 {book_page}：方剂「{formula}」"]
        if composition:
            body.append(f"药物组成：{composition}")
        if notes:
            body.append(f"注意事项：{notes}")
        lines.append("\n".join(body))
        # 书页 → PDF 页（偏移恒定 12，前端跳转用 PDF 页码）
        pdf_page = (int(book_page) + 12) if isinstance(book_page, int) else None
        evidence.append({
            "document_id": f"formula_db:{ref}@p{book_page}",
            "title": f"桂林古本方剂库·{formula}（条文 {ref} · 书页 {book_page}）",
            "content": "\n".join(body[1:]),
            "score": 1.0,  # 精确匹配（非相似度检索），确定性命中记满分
            "pdf_page_start": pdf_page,
            "pdf_page_end": pdf_page,
            "book_page_start": book_page,
            "book_page_end": book_page,
        })
    if len(matches) > 10:
        lines.append(f"（共 {len(matches)} 条匹配，仅展示前 10 条）")
    return "\n".join(lines), evidence


def retrieve_guilinguben(query: str, store, top_k: int) -> Tuple[str, List[Dict[str, Any]]]:
    """执行 FAISS 检索，返回（证据文本, 结构化证据列表）

    索引为 C 轮按条文编号切分的 chunk（一个编号一条数据），metadata 含
    article 条文编号与页码双轨（pdf_page 供前端跳转、book_page 书页供引用展示）。
    """
    hits = store.similarity_search_with_score(query, k=top_k)
    if not hits:
        return "未在《桂林古本伤寒杂病论》索引中检索到相关证据。", []

    evidence = []
    lines = []
    for idx, hit in enumerate(hits, start=1):
        metadata = hit.document.metadata or {}
        source_name = str(metadata.get("source", "unknown-source"))
        article = metadata.get("article", "?")
        page_label = _page_label(
            metadata.get("pdf_page_start"), metadata.get("pdf_page_end"),
            metadata.get("book_page_start"), metadata.get("book_page_end"),
        )
        document_id = f"{source_name}:{article}"
        evidence.append({
            "document_id": document_id,
            "title": f"{source_name}（条文 {article} · {page_label}）",
            "content": hit.document.content,
            "score": normalize_score(hit.score),
            "pdf_page_start": metadata.get("pdf_page_start"),
            "pdf_page_end": metadata.get("pdf_page_end"),
            "book_page_start": metadata.get("book_page_start"),
            "book_page_end": metadata.get("book_page_end"),
        })
        lines.append(f"[{idx}] 出处 {document_id}（{page_label}）\n{hit.document.content}")

    return "\n\n".join(lines), evidence


def _page_label(pdf_start, pdf_end, book_start, book_end) -> str:
    """页码双轨标签：PDF 页（前端跳转）+ 书页（原文引用）；跨页用区间表示"""
    def rng(a, b):
        if a is None:
            return "?"
        if b is None or a == b:
            return str(a)
        return f"{a}-{b}"
    return f"PDF第{rng(pdf_start, pdf_end)}页/书页{rng(book_start, book_end)}"


def execute_tool_call(tool_call: Dict[str, Any], store, top_k: int) -> Tuple[str, List[Dict[str, Any]]]:
    """统一分发执行工具调用，返回（工具结果文本, 检索证据列表（仅检索工具有））"""
    name = tool_call.get("function", {}).get("name", "")
    arguments = tool_call.get("function", {}).get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}

    print(f"[Tools] 执行工具: {name}, 参数: {arguments}")
    if name == "retrieve_guilinguben":
        text, evidence = retrieve_guilinguben(arguments.get("query", ""), store, top_k)
        return text, evidence
    elif name == "lookup_formula":
        return lookup_formula(arguments.get("formula_name", ""))
    else:
        return f"未知工具: {name}", []
