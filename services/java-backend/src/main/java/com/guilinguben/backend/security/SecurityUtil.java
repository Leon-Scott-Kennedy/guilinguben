package com.guilinguben.backend.security;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

/**
 * 安全上下文工具（D 轮 16.40）：从 SecurityContext 取当前登录用户名。
 * 匿名/未登录返回 null（数据隔离落库时对旧数据写 null，保持向后兼容）。
 */
public final class SecurityUtil {

    private SecurityUtil() {
    }

    public static String getCurrentUsername() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated() || "anonymousUser".equals(auth.getPrincipal())) {
            return null;
        }
        return auth.getName();
    }
}
