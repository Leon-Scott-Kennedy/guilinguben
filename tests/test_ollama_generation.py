import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT = ROOT / "services" / "ai-service"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.main import generate_answer


def test_generate_answer_returns_contextual_chinese_summary():
    answer = generate_answer(
        "辨证论治的思路是什么",
        [
            "病机在于阴寒内盛，治宜温经散寒，兼顾宣通经脉。",
            "证候以脉沉细、畏寒为主，需辨明寒凝与虚实。",
        ],
    )

    assert isinstance(answer, str)
    assert len(answer) > 20
    assert any(keyword in answer for keyword in ["辨证", "病机", "阴寒", "温经", "治法"])
