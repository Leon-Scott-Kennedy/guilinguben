package com.guilinguben.backend.repository;

import com.guilinguben.backend.model.AuditLog;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * 审计日志仓库（⑥16.41）：仅查询接口使用（分页 + 按操作类型过滤），写入由 AuditService 直接 save。
 */
@Repository
public interface AuditLogRepository extends JpaRepository<AuditLog, Long> {

    Page<AuditLog> findByAction(String action, Pageable pageable);
}
