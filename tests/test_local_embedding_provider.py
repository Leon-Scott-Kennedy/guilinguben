import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_ROOT = ROOT / "services" / "ai-service"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import settings
from app.retrieval.embedding import LocalEmbeddingProvider


def test_local_embedding_provider_loads_and_embeds_text():
    provider = LocalEmbeddingProvider(model_path=settings.source_pdf_path and str(ROOT / "models" / "bge-large-zh-v1.5"))

    query_vector = provider.embed_query("桂林古本伤寒杂病论中的辨证思路")
    document_vectors = provider.embed_documents([
        "阴寒内盛，脉沉细，宜温经散寒。",
        "表虚兼湿，头痛而身重，宜解表祛湿。",
    ])

    assert isinstance(query_vector, list)
    assert len(query_vector) > 0
    assert len(document_vectors) == 2
    assert all(isinstance(item, list) for item in document_vectors)
    assert all(len(item) == len(query_vector) for item in document_vectors)
