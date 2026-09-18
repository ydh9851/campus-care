package com.campuscare.controller;

import com.campuscare.common.Result;
import com.campuscare.dto.StudentProfile;
import com.campuscare.security.SecurityUtils;
import com.campuscare.service.ProfileService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 学生心理档案接口（一生一档）。
 *
 * 权限设计：
 *   /me            —— 任何登录用户都能看自己的档案
 *   /{userId}      —— 只有辅导员/管理员能看别人的，学生调用会 403
 */
@Tag(name = "06-心理档案", description = "把会话、测评、工单、报告聚合成学生画像")
@RestController
@RequestMapping("/api/profile")
@RequiredArgsConstructor
public class ProfileController {

    private final ProfileService profileService;

    @Operation(summary = "我的心理档案")
    @GetMapping("/me")
    public Result<StudentProfile> me() {
        return Result.ok(profileService.build(SecurityUtils.currentUserId()));
    }

    @Operation(summary = "查看某学生的心理档案（辅导员）",
            description = "由 @PreAuthorize 做方法级鉴权，学生调用返回 HTTP 403 + 统一 JSON")
    @PreAuthorize("hasAnyRole('COUNSELOR', 'ADMIN')")
    @GetMapping("/{userId}")
    public Result<StudentProfile> ofUser(@PathVariable Long userId) {
        return Result.ok(profileService.build(userId));
    }
}
