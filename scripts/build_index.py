"""
独立索引构建脚本
用法: cd services/ai-service && python ../../scripts/build_index.py
      或 python scripts/build_index.py (从项目根目录)

功能:
1. 加载 PDF 文档
2. 解析和清洗文本
3. 生成 Embedding 向量
4. 构建 FAISS 索引
5. 保存索引到磁盘

优势:
- 只需运行一次，后续测试直接加载
- 避免每次测试都重新构建索引
- 大幅缩短测试时间（从 5+ 分钟降到几秒）
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
from app.retrieval.faiss_store import FaissVectorStore
from app.retrieval.pdf_loader import PdfDocumentLoader


def build_and_save_index():
    """构建并保存 FAISS 索引"""
    print("=" * 60)
    print("开始构建 FAISS 索引...")
    print("=" * 60)
    
    # 1. 加载 Embedding 模型
    print("\n[1/4] 加载 BGE Embedding 模型...")
    # Use absolute path for model to ensure it's found regardless of CWD
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
    
    # 3. 构建 FAISS 索引
    print("\n[3/4] 构建 FAISS 索引...")
    store = FaissVectorStore(embeddings)
    store.build_index(documents)
    print("    ✓ FAISS 索引构建完成")
    
    # 4. 保存索引到磁盘
    index_dir = ROOT / "data" / "faiss_index"
    
    # 确保目录存在（使用 absolute path 避免中文路径问题）
    index_dir = index_dir.resolve()
    index_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[4/4] 保存索引到磁盘...")
    print(f"    保存路径: {index_dir}")
    print(f"    目录存在: {index_dir.exists()}")
    
    # 验证目录可写
    test_file = index_dir / "test_write.txt"
    try:
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        print("    ✓ 目录可写")
    except Exception as e:
        print(f"    ✗ 目录不可写: {e}")
        raise
    
    store.save_index(index_dir)
    print("    ✓ 索引保存完成")
    
    # 输出统计信息
    print("\n" + "=" * 60)
    print("索引构建完成！")
    print("=" * 60)
    print(f"文档片段数: {len(documents)}")
    print(f"索引路径:   {index_dir}")
    print(f"索引大小:   约 {_get_dir_size_mb(index_dir):.2f} MB")
    print("\n后续测试将直接加载此索引，无需重新构建。")
    print("=" * 60)


def _get_dir_size_mb(path: Path) -> float:
    """计算目录大小（MB）"""
    total = 0
    for file in path.rglob("*"):
        if file.is_file():
            total += file.stat().st_size
    return total / (1024 * 1024)


if __name__ == "__main__":
    try:
        build_and_save_index()
    except Exception as e:
        print(f"\n❌ 索引构建失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
