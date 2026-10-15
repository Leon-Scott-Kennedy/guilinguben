package com.guilinguben.backend.service;

import com.guilinguben.backend.dto.AnalyzeRequest;
import com.guilinguben.backend.dto.AnalyzeResponse;
import com.guilinguben.backend.dto.ExplainTextRequest;
import com.guilinguben.backend.dto.ExplainTextResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

import java.util.Map;

@Service
public class AiServiceClient {

    private final RestClient restClient;

    // WebClient 仅用于流式（B5）：非阻塞消费 Python 的 SSE 流，长连接不占用 Tomcat 线程；
    // ServerSentEvent 原生解析 id/event/data 字段（Layer 1 事件 id、Layer 2 断点续传的基石，16.30）
    private final WebClient webClient;

    /** 内部 API Key（预留，D 轮 16.40 取舍三）：配置非空时转发请求自动携带 X-Api-Key 头；空 = 不启用 */
    private final String apiKey;

    public AiServiceClient(
            RestClient.Builder builder,
            WebClient.Builder webClientBuilder,
            @Value("${ai-service.base-url:http://localhost:8001}") String baseUrl,
            @Value("${ai-service.api-key:}") String apiKey
    ) {
        this.restClient = builder.baseUrl(baseUrl).build();
        this.webClient = webClientBuilder.baseUrl(baseUrl).build();
        this.apiKey = apiKey;
    }

    /** 构建发往 Python 的请求体（流式/非流式共用）：历史上下文注入到扩展字段 */
    private Map<String, Object> buildBody(AnalyzeRequest request, String historyContext) {
        return Map.of(
            "sessionId", request.sessionId(),
            "question", request.question(),
            "strictMode", request.strictMode(),
            "topK", request.topK(),
            "history_context", historyContext
        );
    }

    public AnalyzeResponse analyze(AnalyzeRequest request, String historyContext) {
        Map<String, Object> body = buildBody(request, historyContext);

        System.out.println("[DEBUG] Sending to Python - history_context length: " + historyContext.length());
        if (!historyContext.isEmpty()) {
            System.out.println("[DEBUG] Sending to Python - history_context preview: " + historyContext.substring(0, Math.min(historyContext.length(), 100)));
        }

        RestClient.RequestBodySpec spec = restClient.post()
                .uri("/api/agent/analyze")
                .contentType(MediaType.APPLICATION_JSON);
        applyApiKey(spec);
        AnalyzeResponse response = spec.body(body)
                .retrieve()
                .body(AnalyzeResponse.class);

        if (response == null) {
            throw new IllegalStateException("AI service returned an empty response");
        }
        return response;
    }

    /** 流式分析：返回 Python SSE 事件流（懒订阅，由调用方决定订阅时机与取消） */
    public Flux<ServerSentEvent<String>> analyzeStream(AnalyzeRequest request, String historyContext) {
        Map<String, Object> body = buildBody(request, historyContext);
        return webClient.post()
                .uri("/api/agent/analyze/stream")
                .contentType(MediaType.APPLICATION_JSON)
                .headers(h -> applyApiKey(h::set))
                .bodyValue(body)
                .retrieve()
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {});
    }

    public ExplainTextResponse explainText(ExplainTextRequest request) {
        RestClient.RequestBodySpec spec = restClient.post()
                .uri("/api/agent/explain")
                .contentType(MediaType.APPLICATION_JSON);
        applyApiKey(spec);
        ExplainTextResponse response = spec.body(request)
                .retrieve()
                .body(ExplainTextResponse.class);

        if (response == null) {
            throw new IllegalStateException("AI service returned an empty explanation");
        }
        return response;
    }

    /** api-key 非空时给请求加 X-Api-Key 头（RestClient 链）；空配置直接跳过（默认不启用） */
    private void applyApiKey(RestClient.RequestBodySpec spec) {
        if (apiKey != null && !apiKey.isBlank()) {
            spec.header("X-Api-Key", apiKey);
        }
    }

    /** api-key 非空时写入头集合（WebClient headers 消费器） */
    private void applyApiKey(java.util.function.BiConsumer<String, String> headerSetter) {
        if (apiKey != null && !apiKey.isBlank()) {
            headerSetter.accept("X-Api-Key", apiKey);
        }
    }
}
