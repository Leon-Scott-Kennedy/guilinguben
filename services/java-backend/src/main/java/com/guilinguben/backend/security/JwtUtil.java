package com.guilinguben.backend.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.List;

/**
 * JWT 工具（D 轮 16.40）：HS256 对称签名，无状态登录态。
 *
 * generateToken 参数化 TTL：当前只签发 access token（jwt.expiration-hours，默认 24h）；
 * refresh token（预留 jwt.refresh-expiration-days）复用同一方法传入更长 TTL 即可，
 * 后续“静默续期”只需在 login 处多签一个并扩展 LoginResponse，无需新增代码路径。
 */
@Component
public class JwtUtil {

    private final SecretKey key;
    private final long expirationHours;

    public JwtUtil(@Value("${jwt.secret}") String secret,
                   @Value("${jwt.expiration-hours:24}") long expirationHours) {
        // HS256 要求密钥 ≥ 256 位（32 字节），密钥过短时启动即失败（快速暴露配置错误）
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expirationHours = expirationHours;
    }

    /** 签发 token：subject=用户名，roles 进 claim 供鉴权过滤器还原权限 */
    public String generateToken(String username, List<String> roles, long ttlHours) {
        return Jwts.builder()
                .subject(username)
                .claim("roles", roles)
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + ttlHours * 3600_000L))
                .signWith(key)
                .compact();
    }

    /** 签发 access token（默认有效期） */
    public String generateAccessToken(String username, List<String> roles) {
        return generateToken(username, roles, expirationHours);
    }

    /**
     * 解析并校验签名与过期：合法返回 Claims，非法/过期/篡改返回 null。
     * 返回 null 时调用方按匿名处理，由 SecurityConfig 授权规则拦 401（fail-closed 语义）。
     */
    public Claims parseToken(String token) {
        try {
            return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
        } catch (JwtException | IllegalArgumentException e) {
            return null;
        }
    }
}
