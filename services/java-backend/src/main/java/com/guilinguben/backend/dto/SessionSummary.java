package com.guilinguben.backend.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

/**
 * 会话列表摘要 DTO（A 轮侧栏会话列表，DeepSeek 风格）：
 * title 为该会话首条提问（空会话为 null，前端显示"新会话"占位），
 * messageCount 为记录条数（一问一答计 1 条），updatedAt 为最后一条记录时间（无记录时取会话创建时间）。
 */
public record SessionSummary(
    @JsonProperty("session_id") String sessionId,
    String title,
    @JsonProperty("message_count") long messageCount,
    @JsonProperty("updated_at") Instant updatedAt
) {
}
