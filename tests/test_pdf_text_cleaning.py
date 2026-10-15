import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT = ROOT / "services" / "ai-service"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.retrieval.pdf_loader import PdfDocumentLoader


def test_pdf_cleaner_removes_control_and_symbol_noise():
    sample = "\u200b故\u2603\u00a0\t病\n\n有\n\n  余\u2060\uFFFD\n\n"
    cleaned = PdfDocumentLoader._clean_text(sample)
    assert "\u200b" not in cleaned
    assert "\u2603" not in cleaned
    assert "\u2060" not in cleaned
    assert "故" in cleaned
    assert "病" in cleaned
    assert "余" in cleaned


def test_pdf_loader_keeps_real_chinese_text_chunks():
    loader = PdfDocumentLoader(ROOT / "桂林古本伤寒杂病论.pdf", min_length=20)
    docs = loader.load()
    assert len(docs) > 0
    assert all(doc.content for doc in docs)
    assert all("\uFFFD" not in doc.content for doc in docs)
    assert all("\u200b" not in doc.content for doc in docs)
