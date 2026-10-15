package com.guilinguben.backend.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.guilinguben.backend.security.JwtAuthenticationFilter;
import jakarta.servlet.DispatcherType;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 安全配置（D 轮 16.40 重写，需求书 16.3 预研落地）：
 * - JWT 无状态鉴权：JwtAuthenticationFilter 解析 Bearer token 注入认证信息；
 * - 放行清单：登录接口（发 token 入口）、健康检查、错误页；
 * - OPTIONS 预检精确放行：跨域预检不携带 Authorization，必须优先放行，否则带自定义头的请求会 401；
 * - ASYNC dispatch 放行：SseEmitter 完成时 Tomcat 会发起 ASYNC dispatch 重入过滤器链，
 *   JwtAuthenticationFilter 是 OncePerRequestFilter 默认跳过该 dispatch，此时 SecurityContext 为空，
 *   若不放行会被 AuthorizationFilter 拒绝 → 响应已提交后异常 → SSE 连接非正常关闭（前端 ERR_INCOMPLETE_CHUNKED_ENCODING）；
 * - 其余接口一律 authenticated；401/403 返回 JSON（前端统一识别后清 token 回登录页）；
 * - 移除 httpBasic/formLogin（原 token-demo 时代产物）；@EnableMethodSecurity 开启方法级 RBAC。
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http,
                                                   JwtAuthenticationFilter jwtFilter,
                                                   AuthenticationEntryPoint entryPoint,
                                                   AccessDeniedHandler accessDeniedHandler) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .cors(org.springframework.security.config.Customizer.withDefaults()) // 跨域规则由控制器 @CrossOrigin 注解声明
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .dispatcherTypeMatchers(DispatcherType.ASYNC).permitAll() // SSE 完成时的异步重入无认证信息（见类注释）
                .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                .requestMatchers("/api/auth/login", "/api/health", "/actuator/health", "/error").permitAll()
                .anyRequest().authenticated()
            )
            .exceptionHandling(e -> e
                .authenticationEntryPoint(entryPoint)
                .accessDeniedHandler(accessDeniedHandler)
            )
            .addFilterBefore(jwtFilter, UsernamePasswordAuthenticationFilter.class)
            .httpBasic(AbstractHttpConfigurer::disable)
            .formLogin(AbstractHttpConfigurer::disable);
        return http.build();
    }

    /** 401 返回 JSON（未登录/token 无效或过期）：前端统一识别后清 token 回登录页 */
    @Bean
    public AuthenticationEntryPoint authenticationEntryPoint(ObjectMapper mapper) {
        return (request, response, ex) -> {
            response.setStatus(401);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(mapper.writeValueAsString(errorBody("未登录或登录已过期")));
        };
    }

    /** 403 返回 JSON（已登录但角色不足）：RBAC 框架的授权失败出口，前端区分提示 */
    @Bean
    public AccessDeniedHandler accessDeniedHandler(ObjectMapper mapper) {
        return (request, response, ex) -> {
            response.setStatus(403);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write(mapper.writeValueAsString(errorBody("无权限执行此操作")));
        };
    }

    /** 统一错误体：data 为 null，不能用 Map.of（Map.of 不允许 null 值，会抛 NPE） */
    private Map<String, Object> errorBody(String message) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("success", false);
        body.put("message", message);
        body.put("data", null);
        return body;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
