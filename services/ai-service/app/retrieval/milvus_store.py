from typing import Any, Callable, Sequence

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from .ports import SearchResult, SourceDocument, VectorStore


class MilvusVectorStore(VectorStore):
    """Milvus adapter implementing the VectorStore protocol (16.33, C 轮字段同步 16.38).

    Score contract: FAISS returns L2 distances (smaller = better) and tools.py
    converts them with normalize_score = 1/(1+d). To keep the caller unchanged,
    this adapter returns a pseudo-L2 distance (1 - cosine similarity) so the
    same formula still yields a monotonic 0~1 relevance score.

    Schema 为 C 轮 6 字段（source/article/页码双轨），与 Chroma 适配器一致。
    """

    DIM = 1024  # bge-large-zh-v1.5 embedding dimension
    BATCH_SIZE = 256
    ALIAS = "default"

    def __init__(
        self,
        embeddings: Any,
        uri: str,
        collection_name: str = "guilinguben_chunks",
    ):
        self.embeddings = embeddings
        self.uri = uri
        self.collection_name = collection_name
        self._collection: Collection | None = None

    # -- lifecycle --

    def collection_exists(self) -> bool:
        """Check whether the target collection already exists on the Milvus server."""
        self._ensure_connection()
        return utility.has_collection(self.collection_name)

    def build_index(self, documents: Sequence[SourceDocument]) -> None:
        """Create (or rebuild) the collection and upsert all documents."""
        self._ensure_connection()
        if utility.has_collection(self.collection_name):
            # Rebuild semantics match FaissVectorStore.build_index: start from scratch
            utility.drop_collection(self.collection_name)

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="article", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="pdf_page_start", dtype=DataType.INT64),
            FieldSchema(name="pdf_page_end", dtype=DataType.INT64),
            FieldSchema(name="book_page_start", dtype=DataType.INT64),
            FieldSchema(name="book_page_end", dtype=DataType.INT64),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.DIM),
        ]
        schema = CollectionSchema(fields, description="桂林古本条文向量库（C 轮按编号切分 + 页码双轨）")
        collection = Collection(self.collection_name, schema=schema)

        for start in range(0, len(documents), self.BATCH_SIZE):
            batch = documents[start:start + self.BATCH_SIZE]
            vectors = self.embeddings.embed_documents([doc.content for doc in batch])
            rows = [
                {
                    "content": doc.content,
                    "source": str(doc.metadata.get("source", "")),
                    "article": str(doc.metadata.get("article", "")),
                    "pdf_page_start": int(doc.metadata.get("pdf_page_start") or 0),
                    "pdf_page_end": int(doc.metadata.get("pdf_page_end") or 0),
                    "book_page_start": int(doc.metadata.get("book_page_start") or 0),
                    "book_page_end": int(doc.metadata.get("book_page_end") or 0),
                    "embedding": vector,
                }
                for doc, vector in zip(batch, vectors)
            ]
            collection.insert(rows)

        collection.flush()
        # IVF_FLAT + COSINE：本地小规模（<10 万条）默认配置，与 FAISS 可比的召回基线
        collection.create_index(
            "embedding",
            {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}},
        )
        collection.load()
        self._collection = collection

    # -- VectorStore protocol --

    def similarity_search(self, query: str, k: int) -> list[SourceDocument]:
        return [result.document for result in self.similarity_search_with_score(query, k)]

    def similarity_search_with_score(self, query: str, k: int) -> list[SearchResult]:
        collection = self._require_collection()
        query_vector = self.embeddings.embed_query(query)
        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=k,
            output_fields=["content", "source", "article", "pdf_page_start", "pdf_page_end", "book_page_start", "book_page_end"],
        )
        hits: list[SearchResult] = []
        for hit in results[0]:
            document = SourceDocument(
                content=hit.entity.get("content"),
                metadata={
                    "source": hit.entity.get("source"),
                    "article": hit.entity.get("article"),
                    "pdf_page_start": hit.entity.get("pdf_page_start"),
                    "pdf_page_end": hit.entity.get("pdf_page_end"),
                    "book_page_start": hit.entity.get("book_page_start"),
                    "book_page_end": hit.entity.get("book_page_end"),
                },
            )
            # 1 - cosine similarity 作为伪 L2 距离，与 FAISS 分数语义对齐
            hits.append(SearchResult(document, float(1.0 - hit.score)))
        return hits

    def as_retriever(self, k: int) -> Callable[[str], list[SourceDocument]]:
        """Agent 工具直接调用 similarity_search_with_score，此接口仅为协议完整性提供。"""

        def _retrieve(query: str) -> list[SourceDocument]:
            return self.similarity_search(query, k)

        return _retrieve

    # -- internals --

    def _ensure_connection(self) -> None:
        if not connections.has_connection(self.ALIAS):
            connections.connect(self.ALIAS, uri=self.uri)

    def _require_collection(self) -> Collection:
        if self._collection is not None:
            return self._collection
        self._ensure_connection()
        if not utility.has_collection(self.collection_name):
            raise RuntimeError(
                f"Milvus collection '{self.collection_name}' 不存在，请先运行灌数脚本 "
                f"scripts/build_milvus_index.py 或切换 vector_backend=faiss"
            )
        self._collection = Collection(self.collection_name)
        self._collection.load()
        return self._collection
