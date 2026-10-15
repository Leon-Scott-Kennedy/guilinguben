package com.guilinguben.backend.repository;

import com.guilinguben.backend.model.AnalysisRecord;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface AnalysisRecordRepository extends JpaRepository<AnalysisRecord, String> {
    // 显式 LIMIT 5：确保只取最近 5 条记录，与 Controller 中“构建历史上下文（最近 5 条记录）”保持一致
    @Query("SELECT r FROM AnalysisRecord r WHERE r.sessionId = :sessionId ORDER BY r.createdAt DESC LIMIT 5")
    List<AnalysisRecord> findTop5BySessionIdOrderByCreatedAtDesc(@Param("sessionId") String sessionId);

    // 分页查询（历史接口分页 16.32）：排序由 Pageable 控制（controller 传倒序）
    Page<AnalysisRecord> findBySessionId(String sessionId, Pageable pageable);

    // 会话记录总数（历史接口分页返回 total 用）
    long countBySessionId(String sessionId);

    /** 数据隔离预留（D 轮 16.40 取舍二）：按属主分页查询；当前读路径未启用（MVP 单用户），启用时历史接口叠加 owner 过滤 */
    Page<AnalysisRecord> findByOwnerUsername(String ownerUsername, Pageable pageable);
}
