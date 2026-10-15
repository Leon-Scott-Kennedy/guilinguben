package com.guilinguben.backend.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;

/**
 * 会话历史上下文缓存（⑤Redis 接线 16.35）。
 *
 * 缓存对象：buildHistoryContext 拼接的最近 5 轮 User/AI 对话文本——每次分析请求都要查库拼接，
 * 属于"读多写少"数据（仅新记录落库时变化），适合 Redis 缓存减少 PostgreSQL 查询。
 *
 * 缓存设计：
 * - Key：guilinguben:history:{sessionId}（业务键前缀区分用途，避免与限流等其它键混淆）
 * - TTL：30 分钟（历史上下文随对话推进变化，TTL 兜底防止脏缓存长期残留；落库时主动 evict）
 * - 失效策略：persistAnalysisRecord/persistFailedRecord 落库成功后调用 evict（写失效，
 *   保证下一轮对话立即拿到含新记录的历史上下文）
 *
 * 容错（fail-open）：Redis 是加速/保护组件而非核心依赖——所有操作 catch 异常仅记日志，
 * 缓存 miss 时上层退回查库路径，服务降级但功能完整。
 */
@Service
public class HistoryCacheService {

    private static final Logger logger = LoggerFactory.getLogger(HistoryCacheService.class);

    private static final String KEY_PREFIX = "guilinguben:history:";
    private static final Duration TTL = Duration.ofMinutes(30);

    private final StringRedisTemplate redisTemplate;

    public HistoryCacheService(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    /** 读取缓存的历史上下文；未命中或 Redis 不可用返回 null（上层退回查库） */
    public String get(String sessionId) {
        try {
            return redisTemplate.opsForValue().get(KEY_PREFIX + sessionId);
        } catch (Exception e) {
            logger.warn("历史上下文缓存读取失败（Redis 不可用？），退回查库: {}", e.getMessage());
            return null;
        }
    }

    /** 写入缓存（空上下文也写入，区分"无历史"与"未缓存"两种状态） */
    public void put(String sessionId, String context) {
        try {
            redisTemplate.opsForValue().set(KEY_PREFIX + sessionId, context, TTL);
        } catch (Exception e) {
            logger.warn("历史上下文缓存写入失败（Redis 不可用？），跳过缓存: {}", e.getMessage());
        }
    }

    /**
     * 写更新：新记录落库后追加到缓存，并裁剪保持“最近 5 轮”与查库（findTop5）语义一致。
     *
     * 为什么不用写失效（evict）：时序上每轮请求内 buildHistoryContext 先 put、落库再 evict，
     * evict 会删掉本请求刚写入的缓存 → 串行对话永远 miss。写更新（append）让连续对话
     * 命中率 100%：首轮 miss 后 put，之后每轮落库都 append，下一轮直接命中。
     *
     * 缓存未建立（本轮请求走查库路径）时不操作：下一轮请求查库后重建。
     */
    public void append(String sessionId, String question, String answer) {
        try {
            String key = KEY_PREFIX + sessionId;
            String current = redisTemplate.opsForValue().get(key);
            if (current == null) {
                return; // 缓存未建立（本轮请求未命中缓存），下轮查库重建，无需更新
            }
            String entry = "User: " + question + "\nAI: " + answer + "\n\n";
            String updated = trimToLastFiveRounds(current + entry);
            redisTemplate.opsForValue().set(key, updated, TTL);
        } catch (Exception e) {
            logger.warn("历史上下文缓存追加失败（Redis 不可用？），依赖下轮查库重建: {}", e.getMessage());
        }
    }

    /** 裁剪为最近 5 轮（每轮以 "User: " 开头），与查库 findTop5 的语义保持一致 */
    private String trimToLastFiveRounds(String context) {
        final String marker = "User: ";
        int count = 0;
        int from = 0;
        int idx;
        while ((idx = context.indexOf(marker, from)) != -1) {
            count++;
            from = idx + 1;
        }
        if (count <= 5) {
            return context;
        }
        // 超过 5 轮：定位倒数第 5 个 "User: " 的位置，从那里截断
        from = 0;
        for (int i = 0; i < count - 5; i++) {
            from = context.indexOf(marker, from) + 1;
        }
        return context.substring(from);
    }
}
