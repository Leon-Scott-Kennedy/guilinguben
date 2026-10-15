package com.guilinguben.backend.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;

/**
 * 会话历史消息 DTO：供前端聊天界面加载历史对话
 * 与 AnalyzeResponse.Citation 复用引用结构，保证前端跳转 PDF 逻辑一致
 */
public record HistoryMessage(
    String question,
    String answer,
    List<AnalyzeResponse.Citation> citations,
    @JsonProperty("created_at") Instant createdAt
) {
}
