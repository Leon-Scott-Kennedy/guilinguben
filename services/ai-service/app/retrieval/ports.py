from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence


@dataclass(frozen=True)
class SourceDocument:
    """A cleaned chunk with enough metadata to explain its source."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    document: SourceDocument
    score: float


class DocumentLoader(Protocol):
    def load(self) -> Sequence[SourceDocument]:
        ...


class VectorStore(Protocol):
    def build_index(self, documents: Sequence[SourceDocument]) -> None:
        ...

    def similarity_search(self, query: str, k: int) -> list[SourceDocument]:
        ...

    def similarity_search_with_score(self, query: str, k: int) -> list[SearchResult]:
        ...

    def as_retriever(self, k: int) -> Any:
        ...
