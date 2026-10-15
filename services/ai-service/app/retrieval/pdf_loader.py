"""PDF 解析器（C 轮重构 16.36）：按条文编号切分 + 三层清洗 + 页码双轨。

切分单位：全文流（按页序拼接），跨页条文天然合并，一个编号 = 一条数据。

清洗策略（坐标定位 + 文本指纹删除——正文会侵入页脚/页眉区，不能按 y 硬切）：
1. 页眉：visitor 模式收集 y>=775 片段（实测纯页眉区：39 种页眉、0 正文误入，
   正文最高 y≈755），按归一化文本从默认文本流删除；
2. 页脚：☯ 页码行（顺带解析书页号）+ 注释块（独立标记行 ①-⑳ 后紧跟含校勘关键词
   （白雲閣/會通/廣西/複刻/勘誤/宋本/成本/本作/底本）的行 → 删除到页尾；
   实测注释块恒为页尾、0 违例，正文引用编号（如"參見【6.15】條注"）随块一并删除）；
3. 正文内联上标 ①-⑨ 保留（"太①過可怪"是条文正文的一部分）。

页码双轨：metadata 同时记录 pdf_page（前端跳转）与 book_page（书页 = PDF页 − 12，
☯ 行实测偏移恒定，供展示引用）。

检索范围：仅 【1.1】~【16.39】（正文页 p13~p172；前言/目录/附录一律不索引）。
"""
import re
import unicodedata
from pathlib import Path
from typing import Sequence

from pypdf import PdfReader

from .ports import DocumentLoader, SourceDocument


class PdfDocumentLoader(DocumentLoader):
    """Parse the PDF into one chunk per 条文编号 (【章.条】), page-aware."""

    ARTICLE_PAT = re.compile(r"[【\[]\s*(\d+)\s*\.\s*(\d+)\s*[】\]]")
    MARKER_PAT = re.compile(r"^[①-⑳¹-⁹]$")
    ANNOTATION_PAT = re.compile(
        r"^(「)|(白雲閣|會通|廣西|複刻|勘誤|宋本|成本|本作|底本|【\s*\d+\s*\.\s*\d+\s*】)"
    )
    BOOK_PAGE_PAT = re.compile(r"·\s*(\d+)\s*·")

    # 版式常量（C1 坐标实验实测）
    HEADER_Y_MIN = 775  # y>=775 为纯页眉区
    MAIN_TEXT_PDF_START = 13  # 正文首页：书页 1 = PDF 第 13 页
    PDF_TO_BOOK_OFFSET = 12  # 书页号 = PDF 页号 − 12
    LAST_ARTICLE = (16, 39)  # 检索范围上限

    def __init__(self, path: str | Path, min_length: int = 10):
        self.path = Path(path)
        self.min_length = min_length

    def load(self) -> Sequence[SourceDocument]:
        page_texts = self.load_cleaned_pages()

        # 记录每页正文在全文流中的偏移区间，供切分时回推页码归属
        flow_parts: list[str] = []
        page_ranges: list[tuple[int, int, int, int]] = []
        offset = 0
        for page_number, book_page, body in page_texts:
            page_ranges.append((page_number, book_page, offset, offset + len(body)))
            flow_parts.append(body)
            offset += len(body)
        flow = "".join(flow_parts)
        return self._split_articles(flow, page_ranges)

    def load_cleaned_pages(self) -> list[tuple[int, int, str]]:
        """页级清洗视图：[(pdf_page, book_page, 清洗后文本)]，仅正文页。

        供需要精确页码的页级提取复用（如方剂库 4 字段重建：
        条目标题所在页的书页号即条目页码，避免 chunk 级 book_page_start 对
        跨页 chunk 第二页条目差 1 的问题）。
        """
        reader = PdfReader(str(self.path))
        main_text_end = self._find_main_text_end(reader)
        page_texts: list[tuple[int, int, str]] = []
        for page_number, page in enumerate(reader.pages, start=1):
            if page_number < self.MAIN_TEXT_PDF_START or page_number > main_text_end:
                continue
            raw_text = page.extract_text() or ""
            book_page = self._parse_book_page(raw_text) or (
                page_number - self.PDF_TO_BOOK_OFFSET
            )
            header_fragments = self._collect_header_fragments(page)
            lines = self._clean_page_lines(raw_text.split("\n"), header_fragments)
            body = "".join(self._clean_line(line) for line in lines)
            if body:
                page_texts.append((page_number, book_page, body))
        return page_texts

    def _find_main_text_end(self, reader: PdfReader) -> int:
        """正文结束页 = 【16.39】首次出现的页（其后为附录，不索引）。"""
        for page_number in range(self.MAIN_TEXT_PDF_START, len(reader.pages) + 1):
            text = reader.pages[page_number - 1].extract_text() or ""
            for m in self.ARTICLE_PAT.finditer(text):
                if (int(m.group(1)), int(m.group(2))) == self.LAST_ARTICLE:
                    return page_number
        raise ValueError("未找到【16.39】条文，无法确定正文结束页")

    def _parse_book_page(self, raw_text: str) -> int | None:
        """从 ☯ 页码行解析书页号；无此行（偶数页）时返回 None 由调用方用偏移推算。"""
        for line in raw_text.split("\n"):
            if "編撰" in line:
                m = self.BOOK_PAGE_PAT.search(line)
                if m:
                    return int(m.group(1))
        return None

    @staticmethod
    def _collect_header_fragments(page) -> set[str]:
        """visitor 模式收集页眉区（y>=775）文本片段，供按指纹删除。"""
        fragments = []

        def visitor(text, cm, tm, font_dict, font_size):
            fragments.append((tm[5], text))

        page.extract_text(visitor_text=visitor)
        return {
            PdfDocumentLoader._normalize(text)
            for y, text in fragments
            if y >= PdfDocumentLoader.HEADER_Y_MIN and text.strip()
        }

    @classmethod
    def _clean_page_lines(cls, raw_lines: list[str], header_fragments: set[str]) -> list[str]:
        """去除 ☯ 页码行、页眉行、注释块（标记行 + 校勘文本，直到页尾）。"""
        kept: list[str] = []
        for i, raw in enumerate(raw_lines):
            line = raw.strip()
            if not line:
                continue
            if cls._is_page_number_line(line):
                continue
            if cls._normalize(line) in header_fragments:
                continue
            if cls.MARKER_PAT.match(line):
                next_line = cls._next_nonempty(raw_lines, i + 1)
                # 下一行是条文编号开头 → 是正文（上标恰好位于条文末尾），不是注释块；
                # 否则按校勘关键词判定注释块（删除到页尾）
                if next_line is not None \
                        and not cls.ARTICLE_PAT.match(next_line) \
                        and cls.ANNOTATION_PAT.search(next_line):
                    break  # 注释块开始：丢弃本行及之后全部（实测注释块恒为页尾）
            kept.append(raw)
        return kept

    @staticmethod
    def _is_page_number_line(line: str) -> bool:
        return line == "☯" or "編撰" in line or bool(re.fullmatch(r"·\s*\d+\s*·", line))

    @staticmethod
    def _next_nonempty(raw_lines: list[str], start: int) -> str | None:
        for j in range(start, len(raw_lines)):
            stripped = raw_lines[j].strip()
            if stripped:
                return stripped
        return None

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", "", text.strip())

    # NFKC 会把圈码 ①-⑳ 与上标 ⁰-⁹ 分解成 ASCII 数字（①→1），
    # 正文上标注记（“太①過可怪”）需保持原形：先占位保护，NFKC 后再还原
    _NFKC_PROTECTED = {
        original: chr(0xE000 + i)
        for i, original in enumerate(
            [chr(c) for c in range(0x2460, 0x2474)]  # ①-⑳
            + [chr(c) for c in (0x00B9, 0x00B2, 0x00B3)]  # ¹²³
            + [chr(c) for c in range(0x2070, 0x207A)]  # ⁰-⁹
        )
    }

    @staticmethod
    def _clean_line(text: str) -> str:
        if not text:
            return ""
        text = text.replace("\u00a0", " ")
        text = text.replace("\ufeff", "")
        protected: dict[str, str] = {}
        for original, placeholder in PdfDocumentLoader._NFKC_PROTECTED.items():
            if original in text:
                protected[placeholder] = original
                text = text.replace(original, placeholder)
        text = unicodedata.normalize("NFKC", text)
        for placeholder, original in protected.items():
            text = text.replace(placeholder, original)
        text = re.sub(r"[\u200b-\u200d\u2060\ufeff]", "", text)
        text = re.sub(r"[\u2500-\u257F\u2600-\u27BF\uE000-\uF8FF]", "", text)
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\s+", "", text)
        return text

    def _split_articles(self, flow: str, page_ranges: list[tuple[int, int, int, int]]) -> list[SourceDocument]:
        """按编号切分全文流；每段的页码归属由其偏移区间与各页区间的重叠关系回推。"""
        matches = list(self.ARTICLE_PAT.finditer(flow))
        documents: list[SourceDocument] = []
        seen: set[str] = set()
        for idx, m in enumerate(matches):
            chapter, article = int(m.group(1)), int(m.group(2))
            if chapter < 1 or chapter > self.LAST_ARTICLE[0]:
                continue
            if chapter == self.LAST_ARTICLE[0] and article > self.LAST_ARTICLE[1]:
                continue
            key = f"{chapter}.{article}"
            if key in seen:
                continue  # 防御：正文引用造成的重复编号只取首个
            seen.add(key)
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(flow)
            segment = flow[m.start():end]
            pages = [
                (p, b) for p, b, s, e in page_ranges
                if s < end and e > m.start()
            ]
            content = re.sub(r"\s+", "", segment)
            if len(content) < self.min_length:
                continue
            pdf_pages = [p for p, _ in pages]
            book_pages = [b for _, b in pages]
            documents.append(SourceDocument(
                content=content,
                metadata={
                    "source": self.path.name,
                    "article": key,
                    "pdf_page_start": pdf_pages[0],
                    "pdf_page_end": pdf_pages[-1],
                    "book_page_start": book_pages[0],
                    "book_page_end": book_pages[-1],
                },
            ))
        return documents
