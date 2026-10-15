package com.guilinguben.backend.model;

import jakarta.persistence.*;

/**
 * 角色（D 轮 16.40 RBAC 框架）。
 * name 为规范值：ADMIN / USER（鉴权时由过滤器加 ROLE_ 前缀生成 authority，与 hasRole 匹配）。
 */
@Entity
@Table(name = "roles")
public class Role {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @Column(nullable = false, unique = true)
    private String name;

    private String description;

    // Getters and Setters
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
}
