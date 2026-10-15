package com.guilinguben.backend.dto;

import com.guilinguben.backend.model.AuditLog;

import java.util.List;

/**
 * 审计日志分页响应（⑥16.41）：避免直接序列化 Spring Data Page（依赖 spring-data-web 的 PageImpl 序列化器）。
 */
public record AuditPageResponse(List<AuditLog> items, long total, int limit, int offset) {
}
