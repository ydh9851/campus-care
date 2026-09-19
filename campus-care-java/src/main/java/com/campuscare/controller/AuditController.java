package com.campuscare.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.campuscare.common.Result;
import com.campuscare.entity.AccessLog;
import com.campuscare.service.AuditService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 访问审计查询接口。
 *
 * 仅限 ADMIN：审计记录的是「哪个辅导员看了哪个学生」，
 * 它本身也是敏感数据。对辅导员开放等于给了他们互相监视的能力，
 * 反而会让人不敢正常使用系统。
 */
@Tag(name = "09-访问审计", description = "敏感数据查阅留痕（仅管理员）")
@RestController
@RequestMapping("/api/audit")
@RequiredArgsConstructor
public class AuditController {

    private final AuditService auditService;

    @Operation(summary = "审计日志分页查询", description = "可按操作人、对象类型与对象 id 过滤")
    @PreAuthorize("hasRole('ADMIN')")
    @GetMapping("/logs")
    public Result<IPage<AccessLog>> logs(@RequestParam(defaultValue = "1") long current,
                                         @RequestParam(defaultValue = "20") long size,
                                         @RequestParam(required = false) Long operatorId,
                                         @RequestParam(required = false) String targetType,
                                         @RequestParam(required = false) Long targetId) {
        return Result.ok(auditService.page(current, size, operatorId, targetType, targetId));
    }
}
