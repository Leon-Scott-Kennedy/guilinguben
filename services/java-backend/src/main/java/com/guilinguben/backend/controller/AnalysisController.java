package com.guilinguben.backend.controller;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.guilinguben.backend.dto.AnalyzeRequest;
import com.guilinguben.backend.dto.AnalyzeResponse;
import com.guilinguben.backend.dto.ApiResponse;
import com.guilinguben.backend.dto.BufferedStreamEvent;
import com.guilinguben.backend.dto.ExplainTextRequest;
import com.guilinguben.backend.dto.ExplainTextResponse;
import com.guilinguben.backend.dto.HistoryMessage;
import com.guilinguben.backend.dto.HistoryPage;
import com.guilinguben.backend.dto.SessionSummary;
import com.guilinguben.backend.model.AnalysisRecord;
import com.guilinguben.backend.model.AnalysisSession;
import com.guilinguben.backend.repository.AnalysisRecordRepository;
import com.guilinguben.backend.repository.AnalysisSessionRepository;
import com.guilinguben.backend.security.SecurityUtil;
import com.guilinguben.backend.service.AiServiceClient;
import com.guilinguben.backend.service.AnalysisStreamService;
import com.guilinguben.backend.service.AuditService;
import com.guilinguben.backend.service.HistoryCacheService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import reactor.core.publisher.Flux;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "http://localhost:3000", allowedHeaders = {"Content-Type", "Authorization", "Last-Event-ID"})
public class AnalysisController {

    private static final Logger logger = LoggerFactory.getLogger(AnalysisController.class);

    /**
     * SSE 事件流 Content-Type：SSE 规范约定事件流为 UTF-8，客户端按响应头 charset 解码；
     * 若缺失则按 ISO-8859-1 解码，中文会被破坏（B5 联调实证：乱码字节被 splitlines 误判换行）。
     * 注意：不能在 emitter.send 时传 MediaType——带 mediaType 的重载走 send(Object) 路径，
     * 绕过 SseEventBuilder 拆包且 StringHttpMessageConverter 不支持该类型（canWrite 失败静默丢事件）；
     * 正确做法是提前设置响应头，Spring 写首条消息时若 Content-Type 已存在则不再覆盖。
     */
    private static final MediaType SSE_UTF8 = new MediaType(MediaType.TEXT_EVENT_STREAM, StandardCharsets.UTF_8);

    private final AiServiceClient aiServiceClient;
    private final AnalysisStreamService streamService;
    private final AnalysisSessionRepository sessionRepository;
    private final AnalysisRecordRepository recordRepository;
    private final HistoryCacheService historyCacheService;
    private final AuditService auditService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public AnalysisController(AiServiceClient aiServiceClient,
                              AnalysisStreamService streamService,
                              AnalysisSessionRepository sessionRepository,
                              AnalysisRecordRepository recordRepository,
                              HistoryCacheService historyCacheService,
                              AuditService auditService) {
        this.aiServiceClient = aiServiceClient;
        this.streamService = streamService;
        this.sessionRepository = sessionRepository;
        this.recordRepository = recordRepository;
        this.historyCacheService = historyCacheService;
        this.auditService = auditService;
    }

    @GetMapping("/analysis/history")
    public ResponseEntity<?> getHistory(
            @RequestParam String sessionId,
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam(defaultValue = "0") int offset) {
        logger.info("查询会话历史: sessionId={}, limit={}, offset={}", sessionId, limit, offset);

        try {
            // 分页语义（16.32）：offset=0 返回最新一页（升序排列），offset 递增则往更早翻页；
            // 实现上按时间倒序取一页后反转为升序，保证前端按时间顺序渲染；limit 限制 1~200
            int safeLimit = Math.min(200, Math.max(1, limit));
            int page = Math.max(0, offset) / safeLimit;
            PageRequest pageable = PageRequest.of(page, safeLimit, Sort.by(Sort.Direction.DESC, "createdAt"));
            Page<AnalysisRecord> recordPage = recordRepository.findBySessionId(sessionId, pageable);
            long total = recordRepository.countBySessionId(sessionId);

            List<AnalysisRecord> records = new ArrayList<>(recordPage.getContent());
            Collections.reverse(records); // 倒序页反转为升序返回

            List<HistoryMessage> messages = new ArrayList<>();
            for (AnalysisRecord rec : records) {
                List<AnalyzeResponse.Citation> citations = List.of();
                if (rec.getCitations() != null && !rec.getCitations().isBlank()) {
                    try {
                        citations = objectMapper.readValue(rec.getCitations(),
                                new TypeReference<List<AnalyzeResponse.Citation>>() {});
                    } catch (Exception e) {
                        logger.warn("解析 citations 失败，返回空引用: id={}, error={}", rec.getId(), e.getMessage());
                    }
                }
                messages.add(new HistoryMessage(rec.getQuestion(), rec.getAnswer(), citations, rec.getCreatedAt()));
            }
            boolean hasMore = (long) offset + messages.size() < total;
            HistoryPage result = new HistoryPage(messages, total, hasMore);
            logger.info("会话历史查询完成: sessionId={}, 本页={} 条, 总数={}, hasMore={}",
                    sessionId, messages.size(), total, hasMore);
            return ResponseEntity.ok(ApiResponse.ok("查询成功", result));
        } catch (Exception e) {
            logger.error("查询会话历史失败: ", e);
            return ResponseEntity.status(500).body(ApiResponse.fail("查询失败: " + e.getMessage()));
        }
    }

    @GetMapping("/analysis/sessions")
    public ResponseEntity<?> listSessions() {
        logger.info("查询会话列表");
        try {
            // 聚合查询返回 [sessionId, 首条提问, 记录数, 最后更新时间]，映射为 SessionSummary 列表（最近活跃在前）
            List<Object[]> rows = sessionRepository.aggregateSessionSummaries();
            List<SessionSummary> sessions = new ArrayList<>();
            for (Object[] row : rows) {
                String sessionId = (String) row[0];
                String title = (String) row[1]; // 空会话（建后未提问）为 null，前端显示占位
                long messageCount = ((Number) row[2]).longValue();
                // timestamptz 在 Hibernate 6 原生查询下可能返回 Instant 或 Timestamp，两者都兼容
                Instant updatedAt = row[3] instanceof java.sql.Timestamp ts
                        ? ts.toInstant()
                        : (Instant) row[3];
                sessions.add(new SessionSummary(sessionId, title, messageCount, updatedAt));
            }
            logger.info("会话列表查询完成: {} 个会话", sessions.size());
            return ResponseEntity.ok(ApiResponse.ok("查询成功", sessions));
        } catch (Exception e) {
            logger.error("查询会话列表失败: ", e);
            return ResponseEntity.status(500).body(ApiResponse.fail("查询失败: " + e.getMessage()));
        }
    }

    @PostMapping("/analysis")
    public ResponseEntity<?> analyze(@RequestBody AnalyzeRequest request, HttpServletRequest httpRequest) {
        long startTime = System.currentTimeMillis();
        String sessionId = request.sessionId();
        String question = request.question();
        String ip = httpRequest.getRemoteAddr();
        String username = SecurityUtil.getCurrentUsername(); // 同步线程捕获，审计埋点复用

        logger.info("[全链路] 收到分析请求: sessionId={}, question={}, strictMode={}, topK={}",
                sessionId, question, request.strictMode(), request.topK());

        // 1. 处理会话持久化（按业务字段 sessionId 查询，而非主键 id）
        getOrCreateSession(sessionId);

        // 2. 构建历史上下文 (最近 5 条记录)
        String historyContext = buildHistoryContext(sessionId);

        try {
            // 3. 调用 Python AI 服务
            logger.info("正在调用 Python AI 服务...");
            AnalyzeResponse aiResponse = aiServiceClient.analyze(request, historyContext);
            logger.info("AI 服务响应成功，回答长度: {} 字符", 
                aiResponse.answer() != null ? aiResponse.answer().length() : 0);
                
            // 4. 持久化分析记录
            persistAnalysisRecord(sessionId, question, aiResponse);

            long elapsed = System.currentTimeMillis() - startTime;
            logger.info("[全链路] 分析完成: sessionId={}, intent={}, citations数={}, warnings数={}, 耗时={}ms",
                    sessionId,
                    aiResponse.intent(),
                    aiResponse.citations() != null ? aiResponse.citations().size() : 0,
                    aiResponse.warnings() != null ? aiResponse.warnings().size() : 0,
                    elapsed);

            // 审计（⑥16.41）：问答成功，detail 记录意图与引用数便于排查
            auditService.record(username, "ANALYZE", sessionId, question,
                    "SUCCESS", elapsed, ip, "intent=" + aiResponse.intent()
                            + ", citations=" + (aiResponse.citations() != null ? aiResponse.citations().size() : 0));
            return ResponseEntity.ok(ApiResponse.ok("分析完成", aiResponse));
        } catch (Exception e) {
            logger.error("分析过程中发生错误: ", e);
            // AI 调用失败时也保留提问记录，避免多轮对话历史中断
            persistFailedRecord(sessionId, question, e.getMessage());
            auditService.record(username, "ANALYZE", sessionId, question,
                    "FAIL", System.currentTimeMillis() - startTime, ip, e.getMessage());
            return ResponseEntity.status(500).body(ApiResponse.fail("分析失败: " + e.getMessage()));
        }
    }

    /**
     * SSE 流式分析（B5）：转发 Python 的 status/answer_delta/done/error 事件流给前端。
     *
     * 断连三件套（需求书 16.30）：
     * - 去重：事件携带每会话自增 id（Layer 1）；
     * - 恢复：前端重连带 Last-Event-ID，从 AnalysisStreamService 缓冲补发（Layer 2）；
     *   缓冲不可用时返回 error(recoverable=true) 引导前端走历史接口 record-level 恢复；
     * - 断连处理：前端断开只停止转发，不取消对 Python 的订阅——Python 继续执行，
     *   done 时照常落库，重连后可从缓冲拿到完整结果。
     */
    @PostMapping("/analysis/stream")
    public SseEmitter analyzeStream(@RequestBody AnalyzeRequest request,
                                    @RequestHeader(value = "Last-Event-ID", required = false) Long lastEventId,
                                    HttpServletRequest httpRequest,
                                    HttpServletResponse response) {
        long startTime = System.currentTimeMillis();
        String sessionId = request.sessionId();
        String question = request.question();
        String ip = httpRequest.getRemoteAddr();
        // 同步线程捕获当前用户名：done 落库/审计回调在异步线程执行，届时 SecurityContext 已清空（16.40 修复）
        String currentUsername = SecurityUtil.getCurrentUsername();
        // 提前声明 charset=UTF-8（send 时不传 mediaType，见 SSE_UTF8 常量注释）
        response.setContentType(SSE_UTF8.toString());
        logger.info("[流式] 收到流式分析请求: sessionId={}, question={}, lastEventId={}",
                sessionId, question, lastEventId);

        // 1. 会话与历史上下文（与 /api/analysis 相同的语义）
        getOrCreateSession(sessionId);
        String historyContext = buildHistoryContext(sessionId);

        // 2. SseEmitter：5 分钟超时（本地模型生成可达 2 分钟）；
        //    断开标志位：断开后不再向前端 send（send 会抛异常），但不取消上游订阅
        SseEmitter emitter = new SseEmitter(300_000L);
        AtomicBoolean clientConnected = new AtomicBoolean(true);
        emitter.onTimeout(() -> clientConnected.set(false));
        emitter.onError(e -> clientConnected.set(false));
        emitter.onCompletion(() -> clientConnected.set(false));

        AnalysisStreamService.StreamForwarder forwarder = new AnalysisStreamService.StreamForwarder() {
            @Override
            public void onEvent(BufferedStreamEvent event) {
                sendIfConnected(emitter, clientConnected, event);
            }

            @Override
            public void onComplete() {
                if (clientConnected.get()) {
                    emitter.complete();
                }
            }

            @Override
            public void onFailure(String errorDataJson) {
                if (clientConnected.get()) {
                    try {
                        emitter.send(SseEmitter.event().name("error").data(errorDataJson));
                    } catch (Exception ignored) {
                    }
                    emitter.complete();
                }
            }
        };

        try {
            // 3. 断连恢复：携带 Last-Event-ID 时优先从活动流缓冲补发（Layer 2）
            if (lastEventId != null && lastEventId > 0) {
                AnalysisStreamService.ActiveStream active = streamService.findActive(sessionId);
                if (active == null) {
                    // 缓冲不可用（Java 重启或流已过期）：引导前端走 record-level 历史恢复
                    logger.warn("[流式] 无可用缓冲，引导历史恢复: sessionId={}, lastEventId={}", sessionId, lastEventId);
                    String data = objectMapper.writeValueAsString(Map.of(
                            "message", "无法从服务端缓冲恢复，请从会话历史恢复",
                            "recoverable", true
                    ));
                    emitter.send(SseEmitter.event().name("error").data(data));
                    emitter.complete();
                    return emitter;
                }
                streamService.attach(active, forwarder, lastEventId);
                return emitter;
            }

            // 4. 首次请求：创建活动流并订阅 Python 上游；done 事件回调里落库 + 审计埋点（异步线程）
            Flux<ServerSentEvent<String>> upstream = aiServiceClient.analyzeStream(request, historyContext);
            AnalysisStreamService.ActiveStream active = streamService.startStream(sessionId, upstream,
                    doneData -> onStreamDone(sessionId, question, doneData, startTime, currentUsername, ip),
                    error -> auditService.record(currentUsername, "ANALYZE_STREAM", sessionId, question,
                            "FAIL", System.currentTimeMillis() - startTime, ip, error.getMessage()));
            streamService.attach(active, forwarder, null);
            return emitter;
        } catch (Exception e) {
            logger.error("[流式] 流式请求处理失败: ", e);
            auditService.record(currentUsername, "ANALYZE_STREAM", sessionId, question,
                    "FAIL", System.currentTimeMillis() - startTime, ip, e.getMessage());
            emitter.completeWithError(e);
            return emitter;
        }
    }

    /** 前端连接仍存活时转发事件；send 失败（断开）置位并停止转发 */
    private void sendIfConnected(SseEmitter emitter, AtomicBoolean connected, BufferedStreamEvent event) {
        if (!connected.get()) {
            return;
        }
        try {
            emitter.send(SseEmitter.event()
                    .id(String.valueOf(event.id()))
                    .name(event.type())
                    .data(event.data()));
        } catch (Exception e) {
            connected.set(false);
            logger.debug("[流式] 前端连接已断开，停止转发（上游继续执行并落库）: {}", e.getMessage());
        }
    }

    /** 会话持久化：按业务字段 sessionId 查询，不存在则创建（流式/非流式共用） */
    private AnalysisSession getOrCreateSession(String sessionId) {
        return sessionRepository.findBySessionId(sessionId)
                .orElseGet(() -> {
                    logger.info("创建新会话: {}", sessionId);
                    AnalysisSession newSession = new AnalysisSession();
                    newSession.setSessionId(sessionId);
                    newSession.setCreatedAt(Instant.now());
                    newSession.setOwnerUsername(SecurityUtil.getCurrentUsername()); // 数据隔离架子（16.40）：写路径落属主，读路径暂不过滤
                    return sessionRepository.save(newSession);
                });
    }

    /** 历史上下文：优先读 Redis 缓存（⑤Redis 16.35），miss 则查库拼接近 5 条并回写缓存 */
    private String buildHistoryContext(String sessionId) {
        String cached = historyCacheService.get(sessionId);
        if (cached != null) {
            logger.info("历史上下文缓存命中: sessionId={}, 长度={}", sessionId, cached.length());
            return cached;
        }
        List<AnalysisRecord> history = recordRepository.findTop5BySessionIdOrderByCreatedAtDesc(sessionId);
        StringBuilder historyContext = new StringBuilder();
        for (int i = history.size() - 1; i >= 0; i--) {
            AnalysisRecord rec = history.get(i);
            historyContext.append("User: ").append(rec.getQuestion()).append("\n");
            historyContext.append("AI: ").append(rec.getAnswer()).append("\n\n");
        }
        logger.info("已加载 {} 条历史记录作为上下文（缓存未命中）", history.size());
        if (!historyContext.isEmpty()) {
            logger.debug("历史上下文预览: {}", historyContext.toString().substring(0, Math.min(historyContext.length(), 200)));
        }
        historyCacheService.put(sessionId, historyContext.toString());
        return historyContext.toString();
    }

    /** 分析记录落库（流式/非流式共用）；同步线程调用时从 SecurityContext 取属主 */
    private void persistAnalysisRecord(String sessionId, String question, AnalyzeResponse aiResponse) throws Exception {
        persistAnalysisRecord(sessionId, question, aiResponse, SecurityUtil.getCurrentUsername());
    }

    /** 分析记录落库（指定属主）：流式 done 回调在异步线程执行时 SecurityContext 已清空，属主由调用方同步捕获传入 */
    private void persistAnalysisRecord(String sessionId, String question, AnalyzeResponse aiResponse, String ownerUsername) throws Exception {
        logger.info("正在持久化分析记录...");
        AnalysisRecord record = new AnalysisRecord();
        record.setSessionId(sessionId);
        record.setQuestion(question);
        record.setAnswer(aiResponse.answer());
        record.setCitations(objectMapper.writeValueAsString(aiResponse.citations()));
        record.setCreatedAt(Instant.now());
        record.setOwnerUsername(ownerUsername); // 数据隔离架子（16.40）：写路径落属主，读路径暂不过滤
        AnalysisRecord savedRecord = recordRepository.save(record);
        historyCacheService.append(sessionId, question, aiResponse.answer()); // 写更新：新记录追加进缓存，下轮直接命中
        logger.info("分析记录持久化成功: id={}", savedRecord.getId());
    }

    /**
     * 流式 done 事件回调（异步线程）：落库 + 审计埋点（⑥16.41）。
     * 落库成功记 ANALYZE_STREAM SUCCESS，解析/落库失败记 FAIL。
     */
    private void onStreamDone(String sessionId, String question, String doneData, long startTime, String ownerUsername, String ip) {
        boolean success = persistAnalysisRecordFromStream(sessionId, question, doneData, startTime, ownerUsername);
        long elapsed = System.currentTimeMillis() - startTime;
        if (success) {
            auditService.record(ownerUsername, "ANALYZE_STREAM", sessionId, question,
                    "SUCCESS", elapsed, ip, null);
        } else {
            auditService.record(ownerUsername, "ANALYZE_STREAM", sessionId, question,
                    "FAIL", elapsed, ip, "流式结果解析/落库失败");
        }
    }

    /** 流式 done 事件落库：解析 done JSON 为 AnalyzeResponse 后复用同一落库逻辑；返回是否成功 */
    private boolean persistAnalysisRecordFromStream(String sessionId, String question, String doneData, long startTime, String ownerUsername) {
        try {
            AnalyzeResponse aiResponse = objectMapper.readValue(doneData, AnalyzeResponse.class);
            persistAnalysisRecord(sessionId, question, aiResponse, ownerUsername);
            long elapsed = System.currentTimeMillis() - startTime;
            logger.info("[流式] 分析完成并落库: sessionId={}, intent={}, citations数={}, 耗时={}ms",
                    sessionId, aiResponse.intent(),
                    aiResponse.citations() != null ? aiResponse.citations().size() : 0, elapsed);
            return true;
        } catch (Exception e) {
            logger.error("[流式] done 结果解析/落库失败: sessionId={}, error={}", sessionId, e.getMessage());
            persistFailedRecord(sessionId, question, "流式结果落库失败: " + e.getMessage(), ownerUsername);
            return false;
        }
    }

    /** AI 调用失败时也保留提问记录，避免多轮对话历史中断；同步线程调用时从 SecurityContext 取属主 */
    private void persistFailedRecord(String sessionId, String question, String errorMessage) {
        persistFailedRecord(sessionId, question, errorMessage, SecurityUtil.getCurrentUsername());
    }

    /** AI 调用失败记录落库（指定属主）：异步线程调用时 SecurityContext 已清空，属主由调用方传入 */
    private void persistFailedRecord(String sessionId, String question, String errorMessage, String ownerUsername) {
        try {
            AnalysisRecord failedRecord = new AnalysisRecord();
            failedRecord.setSessionId(sessionId);
            failedRecord.setQuestion(question);
            failedRecord.setAnswer("分析失败: " + errorMessage);
            failedRecord.setCitations("[]");
            failedRecord.setCreatedAt(Instant.now());
            failedRecord.setOwnerUsername(ownerUsername); // 数据隔离架子（16.40）：写路径落属主，读路径暂不过滤
            recordRepository.save(failedRecord);
            historyCacheService.append(sessionId, question, failedRecord.getAnswer()); // 失败记录同样进入历史上下文，同步追加缓存
            logger.warn("AI 调用失败，已保存失败记录以维持会话上下文: sessionId={}", sessionId);
        } catch (Exception saveEx) {
            logger.error("保存失败记录时出错: ", saveEx);
        }
    }

    @PostMapping("/explain")
    public ResponseEntity<?> explain(@RequestBody ExplainTextRequest request, HttpServletRequest httpRequest) {
        long startTime = System.currentTimeMillis();
        String text = request.question();
        String ip = httpRequest.getRemoteAddr();
        String username = SecurityUtil.getCurrentUsername();
        if (text == null || text.isEmpty()) {
            return ResponseEntity.badRequest().body(ApiResponse.fail("文本不能为空"));
        }
        
        try {
            // 2. 调用 Python AI 服务
            logger.info("正在调用 Python AI 服务...");
            ExplainTextResponse aiResponse = aiServiceClient.explainText(request);
            logger.info("AI 服务响应成功，回答长度: {} 字符", 
                aiResponse.answer() != null ? aiResponse.answer().length() : 0);
            auditService.record(username, "EXPLAIN", null, text,
                    "SUCCESS", System.currentTimeMillis() - startTime, ip, null);
            return ResponseEntity.ok(ApiResponse.ok("解释完成", aiResponse));
        } catch (Exception e) {
            logger.error("解释过程中发生错误: ", e);
            auditService.record(username, "EXPLAIN", null, text,
                    "FAIL", System.currentTimeMillis() - startTime, ip, e.getMessage());
            return ResponseEntity.status(500).body(ApiResponse.fail("解释失败: " + e.getMessage()));
        }
    }
}
