package com.guilinguben.backend.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record AnalyzeResponse(
    @JsonProperty("request_id") String requestId,
    String answer,
    String intent,
    List<Citation> citations,
    List<String> warnings,
    String status
) {
    public record Citation(
        @JsonProperty("document_id") String documentId,
        String title,
        String content,
        double score,
        // 页码双轨（C 轮 16.36）：pdf_page 供前端跳转 PDF，book_page 供展示引用；历史数据可为 null
        @JsonProperty("pdf_page_start") Integer pdfPageStart,
        @JsonProperty("pdf_page_end") Integer pdfPageEnd,
        @JsonProperty("book_page_start") Integer bookPageStart,
        @JsonProperty("book_page_end") Integer bookPageEnd
    ) {
    }
}
