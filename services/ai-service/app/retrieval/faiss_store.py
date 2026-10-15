from pathlib import Path
from typing import Any, Sequence

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from .ports import SearchResult, SourceDocument, VectorStore


class FaissVectorStore(VectorStore):
    """Local MVP adapter; callers depend only on the VectorStore protocol."""

    def __init__(self, embeddings: Any, index_path: str | Path | None = None):
        self.embeddings = embeddings
        self._store: FAISS | None = None
        self.index_path = Path(index_path) if index_path else None

    def build_index(self, documents: Sequence[SourceDocument]) -> None:
        langchain_documents = [
            Document(page_content=document.content, metadata=document.metadata)
            for document in documents
        ]
        self._store = FAISS.from_documents(langchain_documents, self.embeddings)

    def save_index(self, path: str | Path | None = None) -> None:
        """Persist the FAISS index to disk."""
        save_path = Path(path) if path else self.index_path
        if save_path is None:
            raise ValueError("No index path provided for saving")
        
        # 确保目录存在（FAISS save_local 要求目录必须已存在）
        save_path = save_path.resolve()
        save_path.mkdir(parents=True, exist_ok=True)
        
        # 使用 FAISS 原生方法保存，避免 langchain 的路径处理问题
        import faiss
        from langchain_community.docstore.in_memory import InMemoryDocstore
        
        store = self._require_store()
        
        # 保存索引文件
        index_file = save_path / "index.faiss"
        faiss.write_index(store.index, str(index_file))
        
        # 保存 docstore
        docstore_file = save_path / "index.pkl"
        import pickle
        with open(docstore_file, "wb") as f:
            pickle.dump(store.docstore, f)
        
        # 保存 index_to_docstore_id
        id_map_file = save_path / "index_to_docstore_id.pkl"
        with open(id_map_file, "wb") as f:
            pickle.dump(store.index_to_docstore_id, f)

    def load_index(self, path: str | Path | None = None) -> None:
        """Load a previously saved FAISS index from disk."""
        import faiss
        import pickle
        
        load_path = Path(path) if path else self.index_path
        if load_path is None:
            raise ValueError("No index path provided for loading")
        if not load_path.exists():
            raise FileNotFoundError(f"Index not found at {load_path}")
        
        # 加载索引文件
        index_file = load_path / "index.faiss"
        if not index_file.exists():
            raise FileNotFoundError(f"Index file not found: {index_file}")
        
        index = faiss.read_index(str(index_file))
        
        # 加载 docstore
        docstore_file = load_path / "index.pkl"
        with open(docstore_file, "rb") as f:
            docstore = pickle.load(f)
        
        # 加载 index_to_docstore_id
        id_map_file = load_path / "index_to_docstore_id.pkl"
        with open(id_map_file, "rb") as f:
            index_to_docstore_id = pickle.load(f)
        
        # 重建 FAISS 对象
        from langchain_community.vectorstores import FAISS
        from langchain_community.docstore.in_memory import InMemoryDocstore
        
        self._store = FAISS(
            embedding_function=self.embeddings,
            index=index,
            docstore=docstore,
            index_to_docstore_id=index_to_docstore_id,
        )

    def index_exists(self, path: str | Path | None = None) -> bool:
        """Check if a saved index exists at the given path."""
        check_path = Path(path) if path else self.index_path
        if check_path is None:
            return False
        return check_path.exists() and (check_path / "index.faiss").exists()

    def similarity_search(self, query: str, k: int) -> list[SourceDocument]:
        return [
            self._to_source_document(document)
            for document in self._require_store().similarity_search(query, k=k)
        ]

    def similarity_search_with_score(self, query: str, k: int) -> list[SearchResult]:
        return [
            SearchResult(self._to_source_document(document), float(score))
            for document, score in self._require_store().similarity_search_with_score(query, k=k)
        ]

    def as_retriever(self, k: int) -> Any:
        return self._require_store().as_retriever(search_kwargs={"k": k})

    def _require_store(self) -> FAISS:
        if self._store is None:
            raise RuntimeError("Vector index has not been built or loaded")
        return self._store

    @staticmethod
    def _to_source_document(document: Document) -> SourceDocument:
        return SourceDocument(content=document.page_content, metadata=dict(document.metadata))
