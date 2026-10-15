package com.guilinguben.backend.controller;

import com.guilinguben.backend.dto.ApiResponse;
import com.guilinguben.backend.dto.LoginRequest;
import com.guilinguben.backend.dto.LoginResponse;
import com.guilinguben.backend.model.User;
import com.guilinguben.backend.repository.UserRepository;
import com.guilinguben.backend.security.JwtUtil;
import com.guilinguben.backend.service.AuditService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 登录接口（D 轮 16.40 重写）：查库 + BCrypt 校验，成功签发 JWT。
 * 失败统一 401（不区分“用户不存在/密码错误”，避免用户名枚举攻击）。
 */
@RestController
@RequestMapping("/api/auth")
@CrossOrigin(origins = "http://localhost:3000", allowedHeaders = {"Content-Type", "Authorization", "Last-Event-ID"})
public class AuthController {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;
    private final AuditService auditService;

    public AuthController(UserRepository userRepository,
                          PasswordEncoder passwordEncoder,
                          JwtUtil jwtUtil,
                          AuditService auditService) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtUtil = jwtUtil;
        this.auditService = auditService;
    }

    @PostMapping("/login")
    public ResponseEntity<ApiResponse<LoginResponse>> login(@Valid @RequestBody LoginRequest request,
                                                            HttpServletRequest httpRequest) {
        long startTime = System.currentTimeMillis();
        String ip = httpRequest.getRemoteAddr();

        User user = userRepository.findByUsername(request.username()).orElse(null);
        if (user == null || !passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            // 审计：登录失败（响应统一 401 防用户名枚举，但审计日志内部记录真实失败原因供排查）
            auditService.record(request.username(), "LOGIN_FAIL", null, null,
                    "FAIL", System.currentTimeMillis() - startTime, ip, "用户名或密码错误");
            return ResponseEntity.status(401).body(ApiResponse.fail("用户名或密码错误"));
        }

        List<String> roles = user.getRoles().stream()
                .map(role -> role.getName())
                .toList();
        String token = jwtUtil.generateAccessToken(user.getUsername(), roles);
        auditService.record(user.getUsername(), "LOGIN_SUCCESS", null, null,
                "SUCCESS", System.currentTimeMillis() - startTime, ip, null);
        return ResponseEntity.ok(ApiResponse.ok("登录成功",
                new LoginResponse(token, user.getUsername(), roles)));
    }
}
