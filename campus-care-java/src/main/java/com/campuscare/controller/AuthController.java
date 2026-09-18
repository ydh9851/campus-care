package com.campuscare.controller;

import com.campuscare.common.Result;
import com.campuscare.dto.LoginRequest;
import com.campuscare.dto.LoginResponse;
import com.campuscare.dto.RegisterRequest;
import com.campuscare.entity.User;
import com.campuscare.security.SecurityUtils;
import com.campuscare.service.AuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 认证接口：注册 / 登录 / 登出 / 当前用户
 */
@Tag(name = "01-认证", description = "注册、登录、登出")
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @Operation(summary = "学生注册")
    @PostMapping("/register")
    public Result<Map<String, Object>> register(@Valid @RequestBody RegisterRequest request) {
        Long userId = authService.register(request);
        return Result.ok(Map.of("userId", userId));
    }

    @Operation(summary = "登录", description = "返回 JWT，后续请求头带 Authorization: Bearer {token}")
    @PostMapping("/login")
    public Result<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return Result.ok(authService.login(request));
    }

    @Operation(summary = "登出", description = "删除 Redis 中的 token，立即失效")
    @PostMapping("/logout")
    public Result<Void> logout() {
        authService.logout(SecurityUtils.currentUserId());
        return Result.ok();
    }

    @Operation(summary = "当前登录用户")
    @GetMapping("/me")
    public Result<User> me() {
        return Result.ok(authService.currentUser());
    }
}
