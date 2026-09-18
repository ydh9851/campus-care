package com.campuscare.controller;

import com.campuscare.common.Result;
import com.campuscare.dto.Dashboard;
import com.campuscare.service.DashboardService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 辅导员数据看板接口。
 *
 * @PreAuthorize 标在类上 = 这个 Controller 的所有接口都要求辅导员/管理员，
 * 比在 SecurityConfig 里按 URL 前缀写规则更好维护 —— 权限跟着代码走，
 * 挪动了 URL 也不会漏掉（URL 规则是「配置」，类注解是「代码」）。
 */
@Tag(name = "07-数据看板", description = "全局风险态势、时段规律、重点学生")
@RestController
@RequestMapping("/api/dashboard")
@PreAuthorize("hasAnyRole('COUNSELOR', 'ADMIN')")
@RequiredArgsConstructor
public class DashboardController {

    private final DashboardService dashboardService;

    @Operation(summary = "辅导员数据看板", description = "days 支持 3~60，topLimit 支持 3~20，越界会自动收敛")
    @GetMapping
    public Result<Dashboard> dashboard(@RequestParam(defaultValue = "14") int days,
                                       @RequestParam(defaultValue = "8") int topLimit) {
        return Result.ok(dashboardService.build(days, topLimit));
    }
}
