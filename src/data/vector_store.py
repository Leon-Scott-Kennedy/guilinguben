"""FAISS向量索引管理"""
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from src.models.embedding import EmbeddingManager
from typing import List

class VectorStoreManager:
    def __init__(self, embedding_manager: EmbeddingManager, top_k: int = 5):
        self.embedding_manager = embedding_manager
        self.top_k = top_k
        self._vectorstore = None
    
    def build_index(self, texts: List[str], labels: List[str]):
        documents = [Document(page_content=texts[i], metadata={"formula": labels[i]}) for i in range(len(texts))]
        self._vectorstore = FAISS.from_documents(documents, self.embedding_manager.get_embeddings())
        return self._vectorstore
    
    def search(self, query: str, k: int = None):
        if k is None:
            k = self.top_k
        return self._vectorstore.similarity_search_with_score(query, k=k)
    
    def get_retriever(self):
        return self._vectorstore.as_retriever(search_kwargs={"k": self.top_k})
        
    def search_with_scores(self, query: str, k: int = 3) -> List[dict]:
        """
        检索并返回带相似度分数的结果（用于 UI 展示）
        相似度 = 1 - (L2距离² / 2)，范围 [0, 1]
        """
        docs_with_scores = self._vectorstore.similarity_search_with_score(query, k=k)
        results = []
        for doc, score in docs_with_scores:
            # L2距离转余弦相似度（因为 normalize_embeddings=True）
            similarity = 1 - (score ** 2) / 2
            results.append({
                'formula': doc.metadata['formula'],
                'score': similarity,
                'symptom': doc.page_content
            })
        return results