import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT = ROOT / "services" / "ai-service"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from fastapi.testclient import TestClient

from app.main import app


def test_agent_analyze_uses_real_pdf_rag_results():
    client = TestClient(app)
    response = client.post(
        "/api/agent/analyze",
        json={
            "sessionId": "demo-session",
            "question": "辨证论治的思路是什么",
            "strictMode": True,
            "topK": 3,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert len(payload["citations"]) > 0
    assert payload["answer"]
    assert any("辨证" in citation["content"] or "辨证" in payload["answer"] for citation in payload["citations"]) or "根据" in payload["answer"]
