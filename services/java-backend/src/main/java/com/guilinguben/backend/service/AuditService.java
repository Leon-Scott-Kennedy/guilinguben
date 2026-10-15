package com.guilinguben.backend.service;

import com.guilinguben.backend.model.AuditLog;
import com.guilinguben.backend.repository.AuditLogRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * 审计埋点服务（⑥16.41）：业务代码 try/finally 直接调用，不引入 AOP（埋点仅 5 处，切面收益低）。
 * 审计写入失败只记日志，绝不向上抛（审计不能反过来影响业务主流程）。
 */
@Service
public class AuditService {

    private static final Logger logger = LoggerFactory.getLogger(AuditService.class);

    /** 问题摘要截断长度 */
    private static final int QUESTION_MAX = 200;
    /** detail 截断长度 */
    private static final int DETAIL_MAX = 500;

    private final AuditLogRepository auditLogRepository;

    public AuditService(AuditLogRepository auditLogRepository) {
        this.auditLogRepository = auditLogRepository;
    }

    /**
     * 记录一条审计日志。
     *
     * @param username   操作人（登录事件取请求体，业务事件取 JWT；流式异步线程由调用方同步捕获传入）
     * @param action     操作类型（LOGIN_SUCCESS / LOGIN_FAIL / ANALYZE / ANALYZE_STREAM / EXPLAIN）
     * @param sessionId  会话 ID（登录事件传 null）
     * @param question   问题原文（自动截断 200；登录事件传 null）
     * @param result     SUCCESS / FAIL
     * @param durationMs 耗时毫秒（未计算传 null）
     * @param ip         客户端 IP
     * @param detail     失败原因 / 越界拦截 status 等补充信息（自动截断 500；无传 null）
     */
    public void record(String username, String action, String sessionId, String question,
                       String result, Long durationMs, String ip, String detail) {
        try {
            AuditLog log = new AuditLog();
            log.setUsername(username == null ? "anonymous" : username);
            log.setAction(action);
            log.setSessionId(sessionId);
            log.setQuestion(truncate(question, QUESTION_MAX));
            log.setResult(result);
            log.setDurationMs(durationMs);
            log.setIp(ip);
            log.setDetail(truncate(detail, DETAIL_MAX));
            auditLogRepository.save(log);
        } catch (Exception e) {
            // 审计自身异常不影响业务主流程，仅记录日志
            logger.error("[审计] 写入审计日志失败: action={}, error={}", action, e.getMessage());
        }
    }

    private String truncate(String text, int max) {
        if (text == null) {
            return null;
        }
        return text.length() <= max ? text : text.substring(0, max);
    }
}
