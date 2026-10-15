package com.guilinguben.backend.controller;

import com.guilinguben.backend.dto.ApiResponse;
import com.guilinguben.backend.dto.AuditPageResponse;
import com.guilinguben.backend.model.AuditLog;
import com.guilinguben.backend.repository.AuditLogRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 审计日志查询接口（⑥16.41）：
 * - 仅 ADMIN 可查（@PreAuthorize，D 轮 RBAC 架子的第一次实际使用；MVP 单用户场景与 authenticated 等价，
 *   但明确表达"审计数据属管理员能力"的边界，为多用户预留）；
 * - 分页 limit/offset + 按 action 过滤；倒序（最新在前）。
 * 注意：此接口不记审计（读接口不埋点，避免刷库）。
 */
@RestController
@RequestMapping("/api/audit")
@CrossOrigin(origins = "http://localhost:3000", allowedHeaders = {"Content-Type", "Authorization", "Last-Event-ID"})
public class AuditController {

    /** limit 上限，防止一次拉全表 */
    private static final int MAX_LIMIT = 200;

    private final AuditLogRepository auditLogRepository;

    public AuditController(AuditLogRepository auditLogRepository) {
        this.auditLogRepository = auditLogRepository;
    }

    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<AuditPageResponse>> query(
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam(defaultValue = "0") int offset,
            @RequestParam(required = false) String action) {
        int safeLimit = Math.max(1, Math.min(limit, MAX_LIMIT));
        int safeOffset = Math.max(0, offset);
        PageRequest pageRequest = PageRequest.of(safeOffset / safeLimit, safeLimit,
                Sort.by(Sort.Direction.DESC, "id"));

        Page<AuditLog> page = (action == null || action.isBlank())
                ? auditLogRepository.findAll(pageRequest)
                : auditLogRepository.findByAction(action, pageRequest);

        return ResponseEntity.ok(ApiResponse.ok("查询成功",
                new AuditPageResponse(page.getContent(), page.getTotalElements(), safeLimit, safeOffset)));
    }
}
