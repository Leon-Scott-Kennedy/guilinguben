package com.guilinguben.backend.repository;

import com.guilinguben.backend.model.AnalysisSession;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;

@Repository
public interface AnalysisSessionRepository extends JpaRepository<AnalysisSession, String> {
    Optional<AnalysisSession> findBySessionId(String sessionId);

    /**
     * 会话列表聚合查询（A 轮侧栏）：一条 SQL 返回每个会话的 sessionId / 首条提问 / 记录数 / 最后更新时间，
     * 含空会话（无记录的会话 title 为 null，最后更新时间退回会话创建时间）；按最后更新时间倒序（最近活跃在前）。
     * 返回 Object[] 顺序：[0]=session_id(String), [1]=首条提问(String|null), [2]=记录数(Number), [3]=updated_at(Timestamp)
     */
    @Query(value = """
            SELECT s.session_id,
                   (SELECT r.question FROM analysis_records r
                     WHERE r.session_id = s.session_id ORDER BY r.created_at ASC LIMIT 1),
                   (SELECT COUNT(*) FROM analysis_records r WHERE r.session_id = s.session_id),
                   COALESCE((SELECT MAX(r.created_at) FROM analysis_records r WHERE r.session_id = s.session_id),
                            s.created_at)
            FROM analysis_sessions s
            ORDER BY COALESCE((SELECT MAX(r.created_at) FROM analysis_records r WHERE r.session_id = s.session_id),
                              s.created_at) DESC
            """, nativeQuery = true)
    List<Object[]> aggregateSessionSummaries();

    /** 数据隔离预留（D 轮 16.40 取舍二）：按属主查会话；当前读路径未启用（MVP 单用户），启用时会话列表/历史接口叠加 owner 过滤 */
    List<AnalysisSession> findByOwnerUsername(String ownerUsername);
}
