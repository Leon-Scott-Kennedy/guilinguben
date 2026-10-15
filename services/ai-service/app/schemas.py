from pydantic import AliasChoices, BaseModel, Field


class AnalyzeRequest(BaseModel):
    session_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("sessionId", "session_id"),
    )
    question: str = Field(min_length=1, max_length=4000)
    strict_mode: bool = Field(
        default=True,
        validation_alias=AliasChoices("strictMode", "strict_mode"),
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        validation_alias=AliasChoices("topK", "top_k"),
    )
    history_context: str = Field(default="")

class Citation(BaseModel):
    document_id: str
    title: str
    content: str
    score: float = Field(ge=0, le=1)
    # 页码双轨（C 轮 16.36）：pdf_page 供前端跳转 PDF，book_page 供展示引用
    pdf_page_start: int | None = None
    pdf_page_end: int | None = None
    book_page_start: int | None = None
    book_page_end: int | None = None


class AnalyzeResponse(BaseModel):
    request_id: str
    answer: str
    intent: str
    citations: list[Citation]
    warnings: list[str]
    status: str

class ExplainTextRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

class ExplainTextResponse(BaseModel):
    answer: str