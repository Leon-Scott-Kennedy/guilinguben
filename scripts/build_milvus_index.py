"""
Milvus 灌数脚本（16.33）
用法: cd services/ai-service && python ../../scripts/build_milvus_index.py
      或 python scripts/build_milvus_index.py (从项目根目录)

功能:
1. 加载 PDF 文档（复用 PdfDocumentLoader 的切块/清洗逻辑，与 FAISS 数据源一致）
2. 生成 Embedding 向量（复用 LocalEmbeddingProvider，bge-large-zh-v1.5）
3. 建 Milvus collection 并分批 upsert（已存在则 drop 重建）
4. 创建 IVF_FLAT + COSINE 索引并 load

前置: milvus + etcd + minio 容器已启动（docker compose up -d etcd minio milvus）
"""
import sys
from pathlib import Path

# 确定项目根目录和服务目录
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent  # 项目根目录
SERVICE_ROOT = ROOT / "services" / "ai-service"

# 将服务目录添加到 Python 路径
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

print(f"项目根目录: {ROOT}")
print(f"服务目录: {SERVICE_ROOT}")
print()

from app.config import settings
from app.retrieval.embedding import LocalEmbeddingProvider
from app.retrieval.milvus_store import MilvusVectorStore
from app.retrieval.pdf_loader import PdfDocumentLoader


def build_milvus_index():
    """解析 PDF 并灌入 Milvus（已存在 collection 则重建）"""
    print("=" * 60)
    print("开始构建 Milvus 索引...")
    print("=" * 60)

    # 1. 加载 Embedding 模型
    print("\n[1/4] 加载 BGE Embedding 模型...")
    import os
    from pathlib import Path as P
    model_path = settings.embedding_model_path
    if not P(model_path).is_absolute():
        model_path = str(ROOT / model_path)
    print(f"    模型路径: {model_path}")
    provider = LocalEmbeddingProvider(model_path=model_path)
    embeddings = provider.get_embeddings()
    print("    ✓ Embedding 模型加载完成")

    # 2. 加载和解析 PDF
    print("\n[2/4] 解析 PDF 文档...")
    pdf_path = settings.source_pdf_path
    if not P(pdf_path).is_absolute():
        pdf_path = str(ROOT / pdf_path)
    print(f"    PDF 路径: {pdf_path}")
    loader = PdfDocumentLoader(pdf_path)
    documents = loader.load()
    print(f"    ✓ 解析完成，生成 {len(documents)} 个文本片段")

    # 3. 建 collection 并灌数（含向量化，分批 upsert）
    print("\n[3/4] 灌入 Milvus（含向量化，耗时取决于数据量）...")
    print(f"    Milvus 地址: {settings.milvus_uri}")
    print(f"    collection:  {settings.milvus_collection_name}")
    store = MilvusVectorStore(
        embeddings,
        uri=settings.milvus_uri,
        collection_name=settings.milvus_collection_name,
    )
    store.build_index(documents)
    print("    ✓ 灌数与索引构建完成（IVF_FLAT + COSINE，已 load）")

    # 4. 抽查验证
    print("\n[4/4] 抽查检索验证...")
    hits = store.similarity_search_with_score("太阳病 发热 恶寒", k=3)
    for i, hit in enumerate(hits, start=1):
        meta = hit.document.metadata
        print(
            f"    {i}. [{hit.score:.4f}] 条文 {meta.get('article')} "
            f"| pdf {meta.get('pdf_page_start')}-{meta.get('pdf_page_end')} "
            f"| book {meta.get('book_page_start')}-{meta.get('book_page_end')} "
            f"| {hit.document.content[:30]}..."
        )
    if not hits:
        print("    ✗ 检索无结果，请检查灌数是否成功")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"Milvus 索引构建完成！片段数: {len(documents)}")
    print("=" * 60)
    print("提示: 将 config.py 的 vector_backend 改为 milvus（或 .env 中设置 VECTOR_BACKEND=milvus）后重启 ai-service 即生效。")


if __name__ == "__main__":
    try:
        build_milvus_index()
    except Exception as e:
        print(f"\n❌ Milvus 灌数失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
