package com.guilinguben.backend.dto;

import java.util.List;

/**
 * 登录响应（D 轮 16.40）：JWT token + 用户信息。
 * refreshToken 预留：启用“静默续期”时增加该字段（JwtUtil 参数化 TTL 已就绪）。
 */
public record LoginResponse(
        String token,
        String username,
        List<String> roles
) {
}
