package com.guilinguben.backend.dto;

import java.util.List;

/**
 * 会话历史分页响应 DTO（多轮记忆治理·历史接口分页，16.32）
 * messages 为当前页消息（升序排列），total 为会话记录总数，hasMore 表示是否还有更早记录
 */
public record HistoryPage(
    List<HistoryMessage> messages,
    long total,
    boolean hasMore
) {
}
