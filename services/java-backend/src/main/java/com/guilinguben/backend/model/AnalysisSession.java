package com.guilinguben.backend.model;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "analysis_sessions")
public class AnalysisSession {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @Column(nullable = false)
    private String sessionId;

    @Column(nullable = false)
    private Instant createdAt;

    /** 数据隔离架子（D 轮 16.40 取舍二）：会话属主用户名；当前写路径落值、读路径不过滤（MVP 单用户，16.40 卡点已记录限制） */
    private String ownerUsername;

    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
    }

    // Getters and Setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public String getOwnerUsername() { return ownerUsername; }
    public void setOwnerUsername(String ownerUsername) { this.ownerUsername = ownerUsername; }
}
