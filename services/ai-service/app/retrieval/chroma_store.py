from pathlib import Path
from typing import Any, Callable, Sequence

import chromadb

from .ports import SearchResult, SourceDocument, VectorStore


class ChromaVectorStore(VectorStore):
    """Chroma adapter implementing the VectorStore protocol (16.37).

    嵌入式持久化（PersistentClient，本地目录 data/chroma_index），零容器零额外进程。
    Collection 使用 cosine space（hnsw:space=cosine），query 返回的 distance
    = 1 - cosine similarity，与 MilvusVectorStore 的伪 L2 距离语义一致——
    tools.py 的 normalize_score = 1/(1+d) 单调映射无需改动。

    Milvus 验收（16.33）已证明 bge 向量归一化（8 查询 top-5 与 FAISS L2 完全
    重合），故 cosine 排序与 FAISS 等价。
    """

    BATCH_SIZE = 256

    def __init__(
        self,
        embeddings: Any,
        persist_dir: str | Path,
        collection_name: str = "guilinguben_chunks",
    ):
        self.embeddings = embeddings
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None

    # -- lifecycle --

    def collection_exists(self) -> bool:
        """Check whether the target collection already exists in the local persistence."""
        client = self._require_client()
        try:
            client.get_collection(self.collection_name)
            return True
        except Exception:
            return False

    def build_index(self, documents: Sequence[SourceDocument]) -> None:
        """Create (or rebuild) the collection and add all documents."""
        client = self._require_client()
        # Rebuild semantics match FaissVectorStore.build_index: start from scratch
        if self.collection_exists():
            client.delete_collection(self.collection_name)

        collection = client.get_or_create_collection(
            name=self.collection_name,
            # cosine space：distance = 1 - cos，与 Milvus 适配器分数语义对齐
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,  # 显式传向量，不用 Chroma 默认 embedding 函数
        )

        for start in range(0, len(documents), self.BATCH_SIZE):
            batch = documents[start:start + self.BATCH_SIZE]
            vectors = self.embeddings.embed_documents([doc.content for doc in batch])
            collection.add(
                ids=[f"doc{start + i}" for i in range(len(batch))],
                documents=[doc.content for doc in batch],
                embeddings=vectors,
                metadatas=[self._to_chroma_metadata(doc) for doc in batch],
            )

        self._collection = collection

    # -- VectorStore protocol --

    def similarity_search(self, query: str, k: int) -> list[SourceDocument]:
        return [result.document for result in self.similarity_search_with_score(query, k)]

    def similarity_search_with_score(self, query: str, k: int) -> list[SearchResult]:
        collection = self._require_collection()
        query_vector = self.embeddings.embed_query(query)
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[SearchResult] = []
        for doc, meta, distance in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            document = SourceDocument(content=doc, metadata=dict(meta or {}))
            # cosine distance（越小越相似），与 FAISS L2 / Milvus 伪距离同为"距离"语义
            hits.append(SearchResult(document, float(distance)))
        return hits

    def as_retriever(self, k: int) -> Callable[[str], list[SourceDocument]]:
        """Agent 工具直接调用 similarity_search_with_score，此接口仅为协议完整性提供。"""

        def _retrieve(query: str) -> list[SourceDocument]:
            return self.similarity_search(query, k)

        return _retrieve

    # -- internals --

    def _require_client(self) -> chromadb.PersistentClient:
        if self._client is None:
            # PersistentClient 惰性创建：持久化目录不存在时自动创建
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        return self._client

    def _require_collection(self) -> chromadb.Collection:
        if self._collection is not None:
            return self._collection
        client = self._require_client()
        if not self.collection_exists():
            raise RuntimeError(
                f"Chroma collection '{self.collection_name}' 不存在，请先运行灌数脚本 "
                f"scripts/build_chroma_index.py 或切换 vector_backend=faiss"
            )
        self._collection = client.get_collection(self.collection_name)
        return self._collection

    @staticmethod
    def _to_chroma_metadata(doc: SourceDocument) -> dict[str, str | int | float | bool]:
        """Chroma metadata 只接受标量值（str/int/float/bool）。

        loader 输出的 6 字段（source/article/页码双轨）全为 str/int，
        直接透传即可；这里仅做类型保险。
        """
        metadata: dict[str, str | int | float | bool] = {}
        for key, value in doc.metadata.items():
            if isinstance(value, (str, int, float, bool)):
                metadata[key] = value
        return metadata
