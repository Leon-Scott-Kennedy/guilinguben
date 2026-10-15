"""④评测集指标化（16.39）：桂林古本 RAG 评测脚本。

真实链路（Java 8080 /api/analysis 非流式接口），判定 = 规则优先 + 本地 Ollama LLM 语义判定，
输出三项指标：工具调用精度（规则）/ 幻觉率（规则+LLM）/ 任务成功率（规则+LLM）。

用法：
    python scripts/eval_rag.py                        # 全量 20 条
    python scripts/eval_rag.py --only symptom         # 单类别增量
    python scripts/eval_rag.py --skip-llm             # 纯规则快速模式
    python scripts/eval_rag.py --compare <旧报告.json> # 与基线对比指标
"""
import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    from zhconv import convert as _zh_conv
except ImportError:  # zhconv 缺失时退化为原样比对（仅影响繁简容错）
    _zh_conv = lambda text, locale: text  # noqa: E731

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / ".deepeval" / "eval_cases.json"
DEFAULT_REPORT_DIR = ROOT / ".deepeval" / "reports"
JAVA_URL = "http://localhost:8080/api/analysis"
OLLAMA_URL = "http://localhost:11434/api/generate"
JUDGE_MODEL = "qwen2.5:7b"

ARTICLE_PATTERN = re.compile(r"\d+\.\d+")  # 条文编号形如 6.14


def zh(text: str) -> str:
    """繁简归一（繁体→简体），保证药物名等关键词比对不受繁简影响。"""
    return _zh_conv(text or "", "zh-cn")


def extract_articles(text: str) -> set[str]:
    return set(ARTICLE_PATTERN.findall(zh(text)))


def article_set_from_citations(citations: list[dict]) -> set[str]:
    """从 citations 的 title/content 提取条文编号集合（title 形如 'guilinguben.pdf（条文 6.14 · ...）'）。"""
    found: set[str] = set()
    for c in citations:
        found |= extract_articles(str(c.get("title", "")))
        found |= extract_articles(str(c.get("content", "")))
    return found


def ask_java(session_id: str, question: str, strict_mode: bool, timeout: int = 300) -> dict:
    body = json.dumps(
        {"sessionId": session_id, "question": question, "strictMode": strict_mode, "topK": 5},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(JAVA_URL, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["data"]


def ask_ollama(prompt: str, timeout: int = 240) -> str:
    body = json.dumps(
        {"model": JUDGE_MODEL, "prompt": prompt, "stream": False,
         "options": {"temperature": 0, "num_predict": 256}},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))["response"].strip()


def judge_verdict(text: str, positive: str, negative: str) -> tuple[bool, str]:
    """解析 judge 输出：首词为 PASS/CLEAN 类视为通过。"""
    head = text.splitlines()[0].strip().upper() if text else ""
    if head.startswith(positive):
        return True, text
    if head.startswith(negative):
        return False, text
    # judge 输出格式漂移：兜底看整个文本里是否以正面词为主
    return positive in head, text


# ---------------------------------------------------------------- 规则判定

def rule_tool_usage(case: dict, resp: dict) -> tuple[bool, str]:
    """工具选择正确性：intent 匹配 + citations 来源工具符合类别预期。

    严格模式强制检索（系统设计），常识/重复类可走任一合法路径，
    expected_intent 支持列表（任一命中即通过）。
    """
    intent = resp.get("intent")
    citations = resp.get("citations") or []
    cat = case["category"]
    reasons: list[str] = []

    expected = case["expected_intent"]
    if isinstance(expected, str):
        expected = [expected]
    ok_intent = intent in expected
    reasons.append(f"intent={intent}（期望 {expected}）{'✓' if ok_intent else '✗'}")

    if cat in ("symptom",):
        has_retrieval = any(not str(c.get("document_id", "")).startswith("formula_db:") for c in citations)
        ok_tool = bool(citations) and has_retrieval
        reasons.append(f"检索证据 {'✓' if ok_tool else '✗'}（citations={len(citations)}）")
    elif cat == "formula":
        has_formula_db = any(str(c.get("document_id", "")).startswith("formula_db:") for c in citations)
        ok_tool = has_formula_db
        reasons.append(f"方剂库证据 {'✓' if ok_tool else '✗'}")
    elif cat in ("general", "out_of_scope"):
        # 越界类必须无 citations；常识类严格模式下可检索（intent 已在上面把关）
        ok_tool = not citations if cat == "out_of_scope" else True
        reasons.append(f"无 citations {'✓' if ok_tool else '✗'}（实际 {len(citations)}）")
    else:  # repeat：严格模式强制检索，检索/方剂库证据均合法
        ok_tool = bool(citations)
        reasons.append(f"有 citations {'✓' if ok_tool else '✗'}（实际 {len(citations)}）")

    return ok_intent and ok_tool, "；".join(reasons)


def rule_content(case: dict, resp: dict) -> tuple[bool, str]:
    """内容规则：关键条文命中（症状/重复）、方剂名与药物组成（方剂/重复）、回答非空。"""
    answer = zh(resp.get("answer", ""))
    citations = resp.get("citations") or []
    cat = case["category"]
    cit_articles = article_set_from_citations(citations)

    if cat in ("symptom", "repeat") and case.get("required_articles"):
        hit = cit_articles & set(case["required_articles"])
        if not hit:
            return False, f"关键条文未命中（期望 {case['required_articles']}，citations 含 {sorted(cit_articles)}）"
        reasons = [f"关键条文命中 {sorted(hit)}"]
    else:
        reasons = []

    if case.get("required_formulas"):
        title_hit = any(zh(f) in zh(c.get("title", "")) for f in case["required_formulas"] for c in citations)
        answer_hit = any(zh(f) in answer for f in case["required_formulas"])
        # repeat 类第二轮可走检索路径（严格模式强制检索），方剂名出现在答案中即算命中
        hit = title_hit or (answer_hit if cat == "repeat" else False)
        if not hit:
            return False, f"方剂证据缺失（期望 {case['required_formulas']} 出现在 citation title{' 或答案' if cat == 'repeat' else ''}）"
        reasons.append(f"方剂名命中 {case['required_formulas']}（title={title_hit}，answer={answer_hit}）")

    if case.get("required_drugs"):
        drugs_hit = [d for d in case["required_drugs"] if zh(d) in answer]
        if len(drugs_hit) < min(2, len(case["required_drugs"])):
            return False, f"药物组成不完整（答案命中 {drugs_hit}，需 ≥2 味）"
        reasons.append(f"药物组成命中 {drugs_hit}")

    if cat == "general":
        if len(answer.strip()) < 20:
            return False, "回答过短"
        reasons.append(f"回答长度 {len(answer.strip())}")

    if cat == "out_of_scope":
        if not answer.strip():
            return False, "空回答"
        reasons.append(f"回答长度 {len(answer.strip())}")

    return True, "；".join(reasons) if reasons else "无内容规则（LLM 判定为主）"


def rule_reference_hallucination(case: dict, resp: dict) -> tuple[bool, str]:
    """引用类幻觉规则部分：答案中出现的条文编号必须 ⊆ citations 编号集合。"""
    answer_articles = extract_articles(resp.get("answer", ""))
    if not answer_articles:
        return True, "答案无条文编号引用"
    cit_articles = article_set_from_citations(resp.get("citations") or [])
    out = answer_articles - cit_articles
    if out:
        return False, f"答案引用未在证据中的编号 {sorted(out)}（citations 含 {sorted(cit_articles)}）"
    return True, f"编号引用 {sorted(answer_articles)} 均在证据内"


# ---------------------------------------------------------------- LLM 判定

def llm_task_success(case: dict, resp: dict, second_round: dict | None = None) -> tuple[bool, str]:
    cat = case["category"]
    q = case["repeat_question"] if (second_round is not None) else case["question"]
    a = resp.get("answer", "")
    if cat == "out_of_scope":
        # 越界类与常规判定方向相反：正确处理 = 拒绝回答，不是满足用户需求
        prompt = (
            "你是评测员。请判断系统是否正确【拒绝】了这个超出自身范围的问题。\n"
            f"用户问题：{q}\n系统回答：{a}\n"
            "标准：系统应拒绝回答或转移话题（例如说明自身仅支持中医文献问答）。"
            "只要系统没有尝试回答该问题本身（编程/天气/股票/作文），即为正确处理；拒绝详略不影响判定。\n"
            "只输出一个词 PASS 或 FAIL，然后输出一句话理由。"
        )
        text = ask_ollama(prompt)
        ok, reason = judge_verdict(text, "PASS", "FAIL")
        return ok, reason
    if cat == "symptom":
        desc = (
            f"依据《桂林古本》条文回答问题，内容应覆盖条文 {' 或 '.join(case['required_articles'])}"
            "中至少一条对应的症状与治法（任一条命中即可）"
        )
    elif cat == "formula":
        desc = f"给出 {case['required_formulas']} 的药物组成（{', '.join(case['required_drugs'])} 等）"
    elif cat == "general":
        desc = "给出常识性合理解释，不得编造具体条文或方剂证据"
    else:  # repeat
        prev = second_round or {}
        prompt = (
            "你是评测员。用户在第二轮要求重复刚才的回答。\n"
            f"第一轮系统回答核心内容：{prev.get('answer', '')[:200]}\n"
            f"第二轮系统回答：{a}\n"
            "标准：第二轮是否重复了第一轮的核心信息（方剂组成/条文要点）。"
            "核心信息一致即 PASS；用户提问中的指代表述（如“刚才说的”）无需纠结。\n"
            "只输出一个词 PASS 或 FAIL，然后输出一句话理由。"
        )
        text = ask_ollama(prompt)
        ok, reason = judge_verdict(text, "PASS", "FAIL")
        return ok, reason
    prompt = (
        "你是评测员。请判断系统回答是否正确处理了用户问题。\n"
        f"用户问题：{q}\n系统回答：{a}\n正确处理的标准：{desc}\n"
        "宽松判定：答案只要包含标准要求的关键信息即 PASS；表述方式（转述或直接引用）、"
        "信息详略、是否附带额外信息（如煎服方法、条文原文）均不影响判定。\n"
        "只输出一个词 PASS 或 FAIL，然后输出一句话理由。"
    )
    text = ask_ollama(prompt)
    ok, reason = judge_verdict(text, "PASS", "FAIL")
    return ok, reason


def llm_hallucination(case: dict, resp: dict) -> tuple[bool, str]:
    """语义幻觉检测（引用类）：无凭空编造条文/方剂/论断。返回 (是否无幻觉, 理由)。"""
    citations = resp.get("citations") or []
    arts = sorted(article_set_from_citations(citations))
    formulas = [c.get("title", "") for c in citations if str(c.get("document_id", "")).startswith("formula_db:")]
    prompt = (
        "你是严格的中医文献评审员。系统回答声称依据《桂林古本伤寒杂病论》条文或方剂库。\n"
        f"系统回答：{resp.get('answer', '')}\n"
        f"可依赖的条文编号：{arts}（回答中出现的任何条文编号都必须在此列表内）\n"
        f"可依赖的方剂证据：{formulas}\n"
        "检查是否存在：1) 引用不在列表中的条文编号；2) 编造方剂名或药物组成；3) 与证据矛盾或凭空捏造的医学论断。\n"
        "只输出一个词 CLEAN 或 HALLUCINATION，然后输出一句话理由。"
    )
    text = ask_ollama(prompt)
    clean, reason = judge_verdict(text, "CLEAN", "HALLUCINATION")
    return clean, reason


# ---------------------------------------------------------------- 用例执行

def run_case(case: dict, ts: str, skip_llm: bool) -> dict:
    """执行单条用例（repeat 类同 session 两轮），返回逐轮响应 + 判定明细。"""
    session_id = f"eval-{case['id']}-{ts}"
    rounds = case.get("rounds", 1)
    responses: list[dict] = []
    for r in range(rounds):
        question = case["question"] if r == 0 else case["repeat_question"]
        started = time.time()
        resp = ask_java(session_id, question, case.get("strict_mode", True))
        resp["_elapsed"] = round(time.time() - started, 1)
        responses.append(resp)

    primary = responses[0]
    detail: dict = {"case": case["id"], "category": case["category"],
                    "intent": primary.get("intent"),
                    "citations": len(primary.get("citations") or []),
                    "elapsed": primary.get("_elapsed"),
                    "rounds": rounds, "session_id": session_id}

    # 规则判定（每轮）
    for idx, resp in enumerate(responses):
        prefix = "" if rounds == 1 else f"round{idx + 1}_"
        ok_tool, tool_reason = rule_tool_usage(case, resp)
        ok_content, content_reason = rule_content(case, resp)
        ok_ref, ref_reason = rule_reference_hallucination(case, resp)
        detail[f"{prefix}tool_ok"], detail[f"{prefix}tool_reason"] = ok_tool, tool_reason
        detail[f"{prefix}content_ok"], detail[f"{prefix}content_reason"] = ok_content, content_reason
        detail[f"{prefix}ref_ok"], detail[f"{prefix}ref_reason"] = ok_ref, ref_reason

    # LLM 判定
    if not skip_llm:
        ok_task, task_reason = llm_task_success(case, primary, second_round=None)
        detail["llm_task_ok"], detail["llm_task_reason"] = ok_task, task_reason
        if case["category"] in ("symptom", "formula", "repeat", "general"):
            ok_hal, hal_reason = llm_hallucination(case, primary)
            detail["llm_hal_ok"], detail["llm_hal_reason"] = ok_hal, hal_reason
        else:
            detail["llm_hal_ok"], detail["llm_hal_reason"] = True, "越界类不引用文献，不参与幻觉判定"
        if rounds == 2:
            ok_task2, task2_reason = llm_task_success(case, responses[1], second_round=primary)
            detail["round2_llm_task_ok"], detail["round2_llm_task_reason"] = ok_task2, task2_reason
    return detail


def aggregate(details: list[dict], skip_llm: bool) -> dict:
    """聚合三项指标（按类别 + 总体）。"""
    cats = ("symptom", "formula", "general", "out_of_scope", "repeat")
    summary: dict = {"tool_precision": {}, "hallucination": {}, "task_success": {}, "by_category": {}}

    def round_keys(d: dict) -> list[str]:
        return [""] if d["rounds"] == 1 else ["round1_", "round2_"]

    for cat in cats:
        group = [d for d in details if d["category"] == cat]
        if not group:
            continue
        tool_pass = sum(all(d.get(f"{p}tool_ok", True) for p in round_keys(d)) for d in group)
        task_pass = sum(
            (d.get("llm_task_ok") if not skip_llm else d.get("content_ok"))
            and (d.get("round2_llm_task_ok") if d["rounds"] == 2 and not skip_llm else True)
            and (d.get("round2_content_ok") if d["rounds"] == 2 and skip_llm else True)
            for d in group
        )
        summary["tool_precision"][cat] = {"pass": tool_pass, "total": len(group)}
        summary["task_success"][cat] = {"pass": task_pass, "total": len(group)}
        summary["by_category"][cat] = {"pass": tool_pass, "total": len(group)}

        if cat in ("symptom", "formula", "repeat"):
            ref_pass = sum(all(d.get(f"{p}ref_ok", True) for p in round_keys(d)) for d in group)
            if not skip_llm:
                ref_pass = sum(
                    d.get("llm_hal_ok") and all(d.get(f"{p}ref_ok", True) for p in round_keys(d)) for d in group
                )
            summary["hallucination"][cat] = {"pass": ref_pass, "total": len(group), "hallucinated": len(group) - ref_pass}

    summary["tool_precision"]["total"] = {"pass": sum(v["pass"] for v in summary["tool_precision"].values() if v is not None),
                                          "total": sum(v["total"] for v in summary["tool_precision"].values() if v is not None)}
    summary["task_success"]["total"] = {"pass": sum(v["pass"] for v in summary["task_success"].values() if v is not None),
                                        "total": sum(v["total"] for v in summary["task_success"].values() if v is not None)}
    hal_items = summary["hallucination"]
    hal_total = sum(v["total"] for v in hal_items.values())
    hal_pass = sum(v["pass"] for v in hal_items.values())
    summary["hallucination"]["total"] = {"pass": hal_pass, "total": hal_total,
                                         "hallucinated": hal_total - hal_pass}
    return summary


def write_reports(details: list[dict], summary: dict, report_dir: Path, ts: str, skip_llm: bool) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"eval-{ts}.json"
    md_path = report_dir / f"eval-{ts}.md"

    def pct(pair: dict) -> str:
        return f"{pair['pass']}/{pair['total']}（{pair['pass'] / pair['total'] * 100:.0f}%）" if pair["total"] else "n/a"

    tp, ts_, hal = summary["tool_precision"], summary["task_success"], summary["hallucination"]
    mode = "快速模式（纯规则，无 LLM 判定）" if skip_llm else "全量模式（规则 + LLM 判定）"
    lines = [
        f"# 桂林古本 RAG 评测报告（{ts}）",
        f"\n评测模式：{mode}；用例数：{len(details)}（5 类 × 4 条）；链路：Java 8080 → ai-service → Ollama qwen2.5:7b。\n",
        "## 指标汇总\n",
        "| 指标 | 结果 |",
        "| --- | --- |",
        f"| 工具调用精度 | {pct(tp['total'])} |",
        f"| 幻觉率（引用类） | {pct(hal['total'])}（无幻觉为通过） |",
        f"| 任务成功率 | {pct(ts_['total'])} |",
        "\n## 分类别明细\n",
        "| 类别 | 工具调用精度 | 任务成功率 | 幻觉判定 |",
        "| --- | --- | --- | --- |",
    ]
    for cat in ("symptom", "formula", "general", "out_of_scope", "repeat"):
        if cat not in tp or not tp[cat]:
            continue
        hal_cell = pct(hal[cat]) if cat in hal else "不适用"
        lines.append(f"| {cat} | {pct(tp[cat])} | {pct(ts_[cat])} | {hal_cell} |")

    lines += ["\n## 逐条明细\n", "| 用例 | 类别 | intent | citations | 工具 | 内容 | 幻觉(规则) | LLM任务 | LLM幻觉 |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for d in details:
        marks = lambda key: "✓" if d.get(key) else "✗"  # noqa: E731
        if d["rounds"] == 2:
            tool_cell = f"{marks('round1_tool_ok')}/{marks('round2_tool_ok')}"
            content_cell = f"{marks('round1_content_ok')}/{marks('round2_content_ok')}"
            ref_cell = f"{marks('round1_ref_ok')}/{marks('round2_ref_ok')}"
        else:
            tool_cell, content_cell, ref_cell = marks("tool_ok"), marks("content_ok"), marks("ref_ok")
        lines.append(
            f"| {d['case']} | {d['category']} | {d['intent']} | {d['citations']} "
            f"| {tool_cell} | {content_cell} | {ref_cell} "
            f"| {marks('llm_task_ok') if not skip_llm else '-'} "
            f"| {marks('llm_hal_ok') if not skip_llm else '-'} |"
        )

    payload = {"ts": ts, "mode": mode, "summary": summary, "details": details}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path


def compare_with_baseline(summary: dict, baseline_path: Path) -> None:
    base = json.loads(baseline_path.read_text(encoding="utf-8"))["summary"]
    print("\n== 与基线对比 ==")
    for metric in ("tool_precision", "task_success"):
        for key in ("total",):
            old, new = base[metric][key], summary[metric][key]
            old_p, new_p = old["pass"] / old["total"] * 100, new["pass"] / new["total"] * 100
            print(f"{metric}: {old_p:.0f}% → {new_p:.0f}%（{'↑' if new_p >= old_p else '↓'}{abs(new_p - old_p):.0f}pp）")
    old, new = base["hallucination"]["total"], summary["hallucination"]["total"]
    if old["total"] and new["total"]:
        old_p, new_p = old["hallucinated"] / old["total"] * 100, new["hallucinated"] / new["total"] * 100
        print(f"幻觉率: {old_p:.0f}% → {new_p:.0f}%（{'↓' if new_p <= old_p else '↑'}{abs(new_p - old_p):.0f}pp）")


def main() -> None:
    parser = argparse.ArgumentParser(description="桂林古本 RAG 评测（16.39）")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--only", help="只跑指定类别（symptom/formula/general/out_of_scope/repeat）")
    parser.add_argument("--skip-llm", action="store_true", help="纯规则快速模式，跳过 LLM 判定")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--compare", help="与基线 JSON 对比指标")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [c for c in cases if c["category"] == args.only]
        print(f"只跑类别 {args.only}：{len(cases)} 条")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"评测集：{len(cases)} 条；session 前缀 eval-*-{ts}；LLM 判定：{'关' if args.skip_llm else '开'}\n")

    details = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']}（{case['category']}）...", flush=True)
        try:
            details.append(run_case(case, ts, args.skip_llm))
            d = details[-1]
            if d["rounds"] == 2:
                marks_line = (
                    f"工具={d.get('round1_tool_ok')}/{d.get('round2_tool_ok')} "
                    f"内容={d.get('round1_content_ok')}/{d.get('round2_content_ok')} "
                    f"幻觉规则={d.get('round1_ref_ok')}/{d.get('round2_ref_ok')}"
                )
            else:
                marks_line = (
                    f"工具={'✓' if d.get('tool_ok') else '✗'} 内容={'✓' if d.get('content_ok') else '✗'} "
                    f"幻觉规则={'✓' if d.get('ref_ok') else '✗'}"
                )
            print(f"    intent={d['intent']} citations={d['citations']} 耗时={d['elapsed']}s {marks_line}", flush=True)
        except Exception as exc:  # 单条失败不中断整体，记入明细
            details.append({"case": case["id"], "category": case["category"], "error": str(exc)})
            print(f"    ✗ 执行失败: {exc}", flush=True)

    summary = aggregate(details, args.skip_llm)
    json_path = write_reports(details, summary, Path(args.report_dir), ts, args.skip_llm)
    tp, hal, tsk = summary["tool_precision"]["total"], summary["hallucination"]["total"], summary["task_success"]["total"]
    print(f"\n工具调用精度: {tp['pass']}/{tp['total']}（{tp['pass'] / tp['total'] * 100:.0f}%）")
    print(f"幻觉率: {hal['hallucinated']}/{hal['total']}（{hal['hallucinated'] / hal['total'] * 100:.0f}%）" if hal["total"] else "幻觉率: n/a")
    print(f"任务成功率: {tsk['pass']}/{tsk['total']}（{tsk['pass'] / tsk['total'] * 100:.0f}%）")
    print(f"报告: {json_path}")
    if args.compare:
        compare_with_baseline(summary, Path(args.compare))


if __name__ == "__main__":
    main()
