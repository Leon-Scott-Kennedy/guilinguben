"""
方剂库 4 字段重建脚本（C 轮 16.36）

从正文提取方剂条目（ref 条文编号 / book_page 书页 / formula 方剂名 /
composition 药物组成 / notes 注意事项-煎服法），并用附录二/三汤方索引交叉校验。

条目形态（C3 探测实测）：
- 完整条目：{方剂名}方 + 组成（药名+剂量）+ 煎服法（"右N味…"或"右剉…/右剪…"）
- 变方/合方条目：{方剂名}方 + "即…"（组成复用前方，notes 记加减法）
- 提及页（"X湯主之。（方見前）"）不是条目，不收录——附录索引含提及页，
  故交叉校验仅作信息性报告（附录语义 ⊇ 4 字段库语义属预期）

页级提取：标题所在页的书页号 = 条目页码（chunk 级 book_page_start 对跨页
chunk 第二页条目会差 1，页级天然精确）；ref = 标题前最近条文编号（倒查本页，
无则倒查上一页）。实测页尾无真截断条目（3 个疑似全为注释/引用误报），无需跨页续接。

误报过滤：标题前紧邻字符为中文字符 → 嵌在叙述/夹注中（如"書中多次出現
四逆湯方"），跳过；真条目标题前为句号/括号/条文编号。

输出：data/桂林古本方剂提取结果.json（覆盖；原文件备份为 .v1.bak.json）

用法: cd services/ai-service && python ../../scripts/build_formula_db.py
"""
import bisect
import json
import re
import shutil
import sys
from pathlib import Path

from pypdf import PdfReader

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
SERVICE_ROOT = ROOT / "services" / "ai-service"
sys.path.insert(0, str(SERVICE_ROOT))

from app.retrieval.pdf_loader import PdfDocumentLoader

DB_PATH = ROOT / "data" / "桂林古本方剂提取结果.json"
BACKUP_PATH = ROOT / "data" / "桂林古本方剂提取结果.v1.bak.json"

# 字符类含 ext-A（"䗪" U+45EA）；后缀含洗/汁/粉/塞等剂型（非贪婪逐字回溯，
# "蜜煎導方"会正确匹配到"導方"而非"煎方"）
FANG_PAT = re.compile(
    r"[一-龥〇A-Za-z\u3400-\u4DBF]{1,20}?"
    r"(?:湯|散|丸|酒|煎|膏|丹|餅|導|熨|洗|汁|粉|塞)方"
)
ARTICLE_PAT = re.compile(r"【\s*(\d+)\s*\.\s*(\d+)\s*】")
BOUNDARY_PAT = re.compile(r"[右即]")  # 组成段与煎服法段的分界："右N味…"或"即…"
MARKER_PAT = re.compile(r"[①-⑳¹-⁹]")  # 正文上标注记（指向已被移除的页脚注释）
# 误报过滤（after 内容判定，C3 实测）：真条目"方"后紧跟组成（药名+剂量）/
# 上标+组成/变方（即…）/引用（見前…）；提及（主之）与夹注（",均為…"、
# "俱見前"）为误报，跳过。前字符不可靠（真条目前可出现 。 ) ( , ① 页首）
NARRATION_PAT = re.compile(r"^(俱見|主之|,)")


def extract_entries(pages: list[tuple[int, int, str]]) -> list[dict]:
    """页级提取方剂条目：标题所在页 = 精确书页。"""
    entries: list[dict] = []
    prev_page_text = ""
    for _pdf, book, text in pages:
        article_positions = [m.start() for m in ARTICLE_PAT.finditer(text)]
        prev_positions = [m.start() for m in ARTICLE_PAT.finditer(prev_page_text)]
        pos = 0
        while True:
            m = FANG_PAT.search(text, pos)
            if not m:
                break
            title_start, title_end = m.start(), m.end()
            pos = title_end
            after = text[title_end:title_end + 25]
            if not after or NARRATION_PAT.match(after):
                continue  # 误报：提及/夹注中的"X方"字样，非条目标题行
            # 条目结束 = 下一个方剂标题 / 下一个条文编号 / 页尾，取最近者
            end = len(text)
            for cand in (FANG_PAT.search(text, title_end),
                         ARTICLE_PAT.search(text, title_end)):
                if cand and cand.start() < end:
                    end = cand.start()
            # 组成段与煎服法段：以首个"右/即"为界
            boundary = BOUNDARY_PAT.search(text, title_end, end)
            if boundary:
                composition = text[title_end:boundary.start()]
                notes = text[boundary.start():end]
            else:
                composition = ""
                notes = text[title_end:end]
            # ref：标题前最近条文编号（本页倒查；无则上一页末尾倒查）
            i = bisect.bisect_right(article_positions, title_start) - 1
            if i >= 0:
                ref_m = ARTICLE_PAT.search(text, article_positions[i])
            elif prev_positions:
                ref_m = ARTICLE_PAT.search(prev_page_text, prev_positions[-1])
            else:
                ref_m = None
            entries.append({
                "ref": f"{ref_m.group(1)}.{ref_m.group(2)}" if ref_m else "",
                "book_page": book,
                "formula": m.group(0)[:-1],  # 去掉结尾"方"字
                "composition": MARKER_PAT.sub("", composition).strip(),
                "notes": MARKER_PAT.sub("", notes).strip(),
            })
        prev_page_text = text
    return entries


def _normalize_index_name(name: str) -> str:
    """附录索引名对齐提取 formula：清排版空格、去尾"方"字。"""
    name = re.sub(r"\s+", "", name)
    return name[:-1] if name.endswith("方") else name


def parse_appendix_index(reader: PdfReader) -> dict[str, list[int]]:
    """解析附录二/三汤方索引（p174-183）：{方剂名: [书页, ...]}。

    两个附录是同一索引的拼音/笔划双排序，页列表需去重；
    附录三存在条目换行（方剂名一行、页码一行，或页码列表跨多行，
    行尾逗号 = 待续），需合并行。
    """
    index: dict[str, list[int]] = {}
    entry_pat = re.compile(r"^([^,]+), (\d+(?:, \d+)*)$")       # 完整条目：名, 页, 页
    entry_open_pat = re.compile(r"^([^,]+), (\d+(?:, \d+)*),$")  # 行尾逗号：页码待续
    name_only_pat = re.compile(r"^([^,]+),$")                     # 只有方剂名（附录三换行）
    pages_only_pat = re.compile(r"^(\d+(?:, \d+)*)$")            # 纯页码续行

    def add(name: str, pages_str: str) -> None:
        name = _normalize_index_name(name)
        for page in (int(x) for x in pages_str.split(", ") if x.strip()):
            pages = index.setdefault(name, [])
            if page not in pages:
                pages.append(page)

    for pn in range(174, 184):
        text = reader.pages[pn - 1].extract_text() or ""
        pending_name = None
        for line in text.split("\n"):
            s = line.strip()
            if not s:
                continue
            if pages_only_pat.match(s):  # 纯页码行：续给上一个待续条目
                if pending_name is not None:
                    add(pending_name, s)
                continue
            m = entry_open_pat.match(s)
            if m:
                pending_name = m.group(1)
                add(m.group(1), m.group(2))
                continue
            m = entry_pat.match(s)
            if m:
                add(m.group(1), m.group(2))
                pending_name = None
                continue
            m = name_only_pat.match(s)
            if m:
                pending_name = m.group(1)
                continue
            pending_name = None
    return index


def cross_check(entries: list[dict], index: dict[str, list[int]]) -> dict:
    """信息性校验（附录索引含提及页，语义 ⊇ 4 字段库，差异属预期）。"""
    extracted: dict[str, list[int]] = {}
    for e in entries:
        extracted.setdefault(e["formula"], []).append(e["book_page"])
    missing_in_extract = []   # 附录有、正文无条目：多为提及页或附录别名
    missing_in_index = []     # 正文有、附录无：变方/别名，需人工确认
    page_diffs = []           # 页码差：附录多余页多为提及页
    for name, pages in sorted(index.items()):
        got = sorted(extracted.get(name, []))
        if not got:
            missing_in_extract.append((name, pages))
        elif got != sorted(pages):
            page_diffs.append((name, pages, got))
    for name, got in sorted(extracted.items()):
        if name not in index:
            missing_in_index.append((name, sorted(set(got))))
    return {
        "missing_in_extract": missing_in_extract,
        "missing_in_index": missing_in_index,
        "page_diffs": page_diffs,
    }


def main():
    reader = PdfReader(str(ROOT / "guilinguben.pdf"))
    loader = PdfDocumentLoader(ROOT / "guilinguben.pdf")
    pages = loader.load_cleaned_pages()

    entries = extract_entries(pages)
    index = parse_appendix_index(reader)
    report = cross_check(entries, index)

    print(f"正文提取条目: {len(entries)}")
    print(f"附录索引方剂数: {len(index)}")
    print(f"页码差异: {len(report['page_diffs'])}（附录多余页多为提及页）")
    print(f"附录有/正文无: {len(report['missing_in_extract'])}")
    print(f"正文有/附录无: {len(report['missing_in_index'])}")
    for name, pages in report["missing_in_extract"][:15]:
        print(f"  [附录独有] {name}: {pages}")
    for name, got in report["missing_in_index"][:15]:
        print(f"  [正文独有] {name}: {got}")
    for name, pages, got in report["page_diffs"][:10]:
        extra = sorted(set(pages) - set(got))
        print(f"  [页码差] {name}: 附录 {pages} vs 提取 {got}（附录多 {extra}）")

    if DB_PATH.exists():
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"旧库已备份: {BACKUP_PATH.name}")
    DB_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写出: {DB_PATH}（{len(entries)} 条）")


if __name__ == "__main__":
    main()
