package com.guilinguben.backend.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * MVC 配置：注册限流拦截器（⑤Redis 接线 16.35）。
 * 只拦截分析类写接口（非流式 + 流式）——这两个接口会触发 LLM 推理（最昂贵资源），
 * 历史/列表等只读接口不消耗 LLM 不限流。
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final RateLimitInterceptor rateLimitInterceptor;

    public WebConfig(RateLimitInterceptor rateLimitInterceptor) {
        this.rateLimitInterceptor = rateLimitInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(rateLimitInterceptor)
                .addPathPatterns("/api/analysis", "/api/analysis/stream");
    }
}
