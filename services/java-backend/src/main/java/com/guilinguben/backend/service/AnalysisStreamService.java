package com.guilinguben.backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.guilinguben.backend.dto.BufferedStreamEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Service;
import reactor.core.Disposable;
import reactor.core.publisher.Flux;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Consumer;

/**
 * 流式会话管理（B5 Layer 2）：按会话维护进行中的 SSE 活动流。
 *
 * 职责：
 * 1. 订阅 Python 上游流，事件分配每会话自增 id（Layer 1，去重依赖）后写入内存缓冲；
 * 2. 事件广播给当前连接的前端转发器（SseEmitter 包装）；
 * 3. 前端断连后不取消上游订阅（让 Python 跑完并落库），缓冲保留 TTL 供重连补发
 *    （Last-Event-ID 续传）；流结束后缓冲保留 5 分钟，过期惰性清理。
 *
 * 恢复分层取舍（需求书 16.30）：Layer 3（Python last_event_id 重订）与
 * Layer 4（Redis/DB 持久化 offset）不做——本地单机场景收益低，Java 重启后
 * 前端应走 record-level 历史接口恢复（controller 引导）。
 */
@Service
public class AnalysisStreamService {

    private static final Logger logger = LoggerFactory.getLogger(AnalysisStreamService.class);

    /** 每会话事件缓冲上限：超出从头部淘汰（防内存膨胀） */
    private static final int MAX_BUFFERED_EVENTS = 2000;
    /** 流结束后缓冲保留时长（毫秒）：供断连重连重放 */
    private static final long BUFFER_TTL_MILLIS = 5 * 60 * 1000L;

    private final Map<String, ActiveStream> activeStreams = new ConcurrentHashMap<>();
    private final ObjectMapper objectMapper;

    public AnalysisStreamService(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    /** 前端连接转发器：SseEmitter 的包装，由 controller 实现（发送/完成/失败） */
    public interface StreamForwarder {
        void onEvent(BufferedStreamEvent event);

        void onComplete();

        void onFailure(String errorDataJson);
    }

    /** 会话级活动流：事件缓冲 + 转发器列表 + 上游订阅生命周期 */
    public static class ActiveStream {
        final String sessionId;
        //事件缓冲
        final List<BufferedStreamEvent> buffer = new CopyOnWriteArrayList<>();
        final AtomicLong eventCounter = new AtomicLong(0);
        //转发器列表
        final List<StreamForwarder> forwarders = new CopyOnWriteArrayList<>();
        final AtomicBoolean finished = new AtomicBoolean(false);
        volatile long finishedAt = 0L;
        //上游订阅生命周期
        volatile Disposable upstream;

        ActiveStream(String sessionId) {
            this.sessionId = sessionId;
        }
    }

    /**
     * 创建会话活动流并订阅 Python 上游。
     *
     * @param sessionId    会话 ID（新分析请求会覆盖同会话旧流，旧流仍跑完落库）
     * @param upstream     Python SSE 事件流
     * @param doneHandler  done 事件回调（controller 落库）
     * @param errorHandler 上游 error 回调（controller 审计埋点，可为 null）
     */
    public ActiveStream startStream(String sessionId, Flux<ServerSentEvent<String>> upstream,
                                    Consumer<String> doneHandler, Consumer<Throwable> errorHandler) {
        ActiveStream stream = new ActiveStream(sessionId);
        activeStreams.put(sessionId, stream);
        logger.info("[流式] 创建会话活动流: sessionId={}", sessionId);

        stream.upstream = upstream.subscribe(
                sse -> onUpstreamEvent(stream, sse, doneHandler),
                error -> onUpstreamError(stream, error, errorHandler),
                () -> onUpstreamComplete(stream)
        );
        return stream;
    }

    /** 查找会话活动流（惰性清理：流结束后超过 TTL 的缓冲视为不可恢复） */
    public ActiveStream findActive(String sessionId) {
        ActiveStream stream = activeStreams.get(sessionId);
        if (stream == null) {
            return null;
        }
        if (stream.finished.get() && System.currentTimeMillis() - stream.finishedAt > BUFFER_TTL_MILLIS) {
            activeStreams.remove(sessionId, stream);
            return null;
        }
        return stream;
    }

    /**
     * 挂接前端转发器：lastEventId 存在时先重放缓冲中其后的事件（Layer 2 短断连补发），
     * 再注册为广播接收者；流已结束则重放后直接 complete。
     */
    public void attach(ActiveStream stream, StreamForwarder forwarder, Long lastEventId) {
        if (lastEventId != null && lastEventId > 0) {
            int replayed = 0;
            for (BufferedStreamEvent event : stream.buffer) {
                if (event.id() > lastEventId) {
                    forwarder.onEvent(event);
                    replayed++;
                }
            }
            logger.info("[流式] 断连恢复重放: sessionId={}, lastEventId={}, 补发{}条", stream.sessionId, lastEventId, replayed);
        }
        if (stream.finished.get()) {
            forwarder.onComplete();
            return;
        }
        stream.forwarders.add(forwarder);
    }

    /** 前端断开：仅移除转发器，不取消上游订阅（Python 继续执行，结果照常落库） */
    public void detach(ActiveStream stream, StreamForwarder forwarder) {
        stream.forwarders.remove(forwarder);
        logger.debug("[流式] 前端转发器断开: sessionId={}, 剩余转发器={}", stream.sessionId, stream.forwarders.size());
    }

    private void onUpstreamEvent(ActiveStream stream, ServerSentEvent<String> sse, Consumer<String> doneHandler) {
        String type = sse.event() != null ? sse.event() : "message";
        String data = sse.data() != null ? sse.data() : "";
        BufferedStreamEvent event = new BufferedStreamEvent(stream.eventCounter.incrementAndGet(), type, data);
        appendBuffer(stream, event);
        broadcast(stream, event);

        if ("done".equals(type)) {
            stream.finished.set(true);
            stream.finishedAt = System.currentTimeMillis();
            try {
                doneHandler.accept(data);
            } catch (Exception e) {
                logger.error("[流式] done 落库失败: sessionId={}, error={}", stream.sessionId, e.getMessage());
            }
            completeForwarders(stream);
            stream.upstream.dispose();
        }
    }

    private void onUpstreamError(ActiveStream stream, Throwable error, Consumer<Throwable> errorHandler) {
        logger.error("[流式] Python 上游异常: sessionId={}, error={}", stream.sessionId, error.getMessage());
        if (errorHandler != null) {
            try {
                errorHandler.accept(error); // controller 审计埋点（⑥16.41）；异常不影响流收尾
            } catch (Exception e) {
                logger.debug("[流式] error 回调执行失败: {}", e.getMessage());
            }
        }
        stream.finished.set(true);
        stream.finishedAt = System.currentTimeMillis();
        try {
            String data = objectMapper.writeValueAsString(Map.of(
                    "message", "AI 服务流式处理失败: " + error.getMessage(),
                    "recoverable", false
            ));
            BufferedStreamEvent event = new BufferedStreamEvent(stream.eventCounter.incrementAndGet(), "error", data);
            appendBuffer(stream, event);
            broadcast(stream, event);
        } catch (Exception e) {
            logger.error("[流式] 构造 error 事件失败: {}", e.getMessage());
        }
        completeForwarders(stream);
    }

    private void onUpstreamComplete(ActiveStream stream) {
        if (!stream.finished.get()) {
            logger.warn("[流式] Python 流结束但未收到 done 事件: sessionId={}", stream.sessionId);
            stream.finished.set(true);
            stream.finishedAt = System.currentTimeMillis();
            completeForwarders(stream);
        }
    }

    private void appendBuffer(ActiveStream stream, BufferedStreamEvent event) {
        stream.buffer.add(event);
        while (stream.buffer.size() > MAX_BUFFERED_EVENTS) {
            stream.buffer.remove(0);
        }
    }

    private void broadcast(ActiveStream stream, BufferedStreamEvent event) {
        for (StreamForwarder forwarder : stream.forwarders) {
            try {
                forwarder.onEvent(event);
            } catch (Exception e) {
                logger.debug("[流式] 转发失败（前端已断开）: {}", e.getMessage());
                stream.forwarders.remove(forwarder);
            }
        }
    }

    private void completeForwarders(ActiveStream stream) {
        for (StreamForwarder forwarder : stream.forwarders) {
            try {
                forwarder.onComplete();
            } catch (Exception e) {
                logger.debug("[流式] complete 通知失败: {}", e.getMessage());
            }
        }
        stream.forwarders.clear();
    }
}
