package com.guilinguben.backend.dto;

/**
 * 流式事件缓冲记录（B5 Layer 2）：按会话缓存已转发给前端的 SSE 事件，
 * 支持断连重连时按 Last-Event-ID 补发剩余事件（恢复分层设计见需求书 16.30）。
 *
 * @param id   事件自增序号（每会话独立递增，Layer 1 去重依赖）
 * @param type 事件类型（status / answer_delta / done / error，与 Python 端协议一致）
 * @param data 事件数据（JSON 字符串，转发时原样透传）
 */
public record BufferedStreamEvent(long id, String type, String data) {
}
