package com.guilinguben.backend.model;

import jakarta.persistence.*;
import java.time.Instant;

/**
 * 审计日志（⑥审计日志与调用指标，16.41）：重要操作流水表。
 * 记录范围 = 登录成功/失败、问答（含越界拦截等正常业务结果）、流式问答、选词解释；
 * 读接口（history/sessions）不记（避免查询类操作刷库）。
 * 自增 Long 主键（流水表标准做法，区别于业务实体的 UUID），查询按 id 倒序。
 */
@Entity
@Table(name = "audit_logs")
public class AuditLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** 操作人：登录事件取请求体用户名，业务事件取 JWT（D 轮 16.40） */
    @Column(nullable = false)
    private String username;

    /** 操作类型：LOGIN_SUCCESS / LOGIN_FAIL / ANALYZE / ANALYZE_STREAM / EXPLAIN */
    @Column(nullable = false)
    private String action;

    /** 会话 ID（登录事件为 null） */
    private String sessionId;

    /** 问题摘要（截断 200 字符；登录事件为 null） */
    @Column(length = 200)
    private String question;

    /** 结果：SUCCESS / FAIL；越界拦截属正常业务结果记 SUCCESS（detail 注明 status=BLOCKED） */
    @Column(nullable = false)
    private String result;

    /** 操作耗时（毫秒） */
    private Long durationMs;

    /** 客户端 IP（HttpServletRequest.getRemoteAddr） */
    private String ip;

    /** 补充信息：失败原因 / 越界拦截 status 等（截断 500 字符） */
    @Column(length = 500)
    private String detail;

    @Column(nullable = false)
    private Instant createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }
    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }
    public String getQuestion() { return question; }
    public void setQuestion(String question) { this.question = question; }
    public String getResult() { return result; }
    public void setResult(String result) { this.result = result; }
    public Long getDurationMs() { return durationMs; }
    public void setDurationMs(Long durationMs) { this.durationMs = durationMs; }
    public String getIp() { return ip; }
    public void setIp(String ip) { this.ip = ip; }
    public String getDetail() { return detail; }
    public void setDetail(String detail) { this.detail = detail; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
}
