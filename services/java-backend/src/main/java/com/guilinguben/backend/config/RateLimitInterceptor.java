package com.guilinguben.backend.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;

/**
 * 接口限流拦截器（⑤Redis 接线 16.35）：固定窗口计数算法。
 *
 * 原理（固定窗口）：
 * - Key 携带当前分钟窗口号（epochSecond/60），每分钟自然滚动出新的 Key；
 * - 每次请求对 Key 执行 INCR（Redis 单线程原子自增，天然并发安全）；
 * - 首次自增（返回 1）时设置 EXPIRE，窗口过期后 Key 自动删除；
 * - 计数超过阈值（30 次/分钟/IP）返回 429 + 友好 JSON，附 Retry-After 引导重试。
 *
 * 为什么选固定窗口而非滑动窗口/令牌桶：本地单用户场景请求量小，固定窗口实现简单、
 * 面试可讲清原理；滑动窗口（ZSET）与令牌桶（Lua 脚本）适合高并发精确控速，可作扩展话题。
 *
 * 容错（fail-open）：限流是保护性功能，Redis 不可用时放行请求仅记日志——
 * 不能因为限流组件故障阻断核心问答链路（可用性优先于保护）。
 */
@Component
public class RateLimitInterceptor implements HandlerInterceptor {

    private static final Logger logger = LoggerFactory.getLogger(RateLimitInterceptor.class);

    /** 每 IP 每分钟允许的最大分析请求数（本地 LLM 单次生成 1~2 分钟，正常前端串行远达不到） */
    private static final int MAX_REQUESTS_PER_MINUTE = 30;
    /** 过期时间略大于窗口长度，防止边界时刻 Key 提前消失导致计数重置 */
    private static final Duration KEY_TTL = Duration.ofSeconds(120);

    private final StringRedisTemplate redisTemplate;

    public RateLimitInterceptor(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        try {
            String ip = resolveClientIp(request);
            long window = Instant.now().getEpochSecond() / 60;
            String key = buildIpKey(ip, window); // D 轮 16.40 取舍三：限流保持 IP 维度（按用户限流的 key 设计已预留，见 buildUserKey）

            Long count = redisTemplate.opsForValue().increment(key);
            if (count != null && count == 1L) {
                redisTemplate.expire(key, KEY_TTL);
            }
            if (count != null && count > MAX_REQUESTS_PER_MINUTE) {
                logger.warn("限流触发: ip={}, 本窗口请求数={}", ip, count);
                response.setStatus(429);
                response.setHeader("Retry-After", "60");
                response.setContentType("application/json");
                response.setCharacterEncoding(StandardCharsets.UTF_8.name());
                response.getWriter().write(
                        "{\"success\":false,\"message\":\"请求过于频繁，请稍后再试\",\"data\":null}");
                return false;
            }
        } catch (Exception e) {
            // Redis 不可用：fail-open 放行（限流是保护性功能，不阻断核心链路）
            logger.warn("限流检查失败（Redis 不可用？），放行请求: {}", e.getMessage());
        }
        return true;
    }

    /** 客户端 IP：优先取 X-Forwarded-For 首个地址（代理场景），否则回退 RemoteAddr */
    private String resolveClientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }

    /** Redis key 构建：当前按 IP 维度限流（D 轮 16.40 取舍三：保持 IP 维度不变） */
    private String buildIpKey(String ip, long window) {
        return "guilinguben:ratelimit:" + ip + ":" + window;
    }

    /**
     * 按用户名限流的 key 设计预留（未启用，D 轮 16.40 取舍三）：
     * 启用时 preHandle 改为取 SecurityUtil.getCurrentUsername() 分支调用本方法，
     * 即可把限流维度从“IP”切换到“登录用户”（同一用户跨 IP 共用配额）。
     */
    private String buildUserKey(String username, long window) {
        return "guilinguben:ratelimit:user:" + username + ":" + window;
    }
}
