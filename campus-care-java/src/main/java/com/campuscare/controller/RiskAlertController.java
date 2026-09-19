package com.campuscare.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.campuscare.common.Result;
import com.campuscare.entity.RiskAlert;
import com.campuscare.security.SecurityUtils;
import com.campuscare.service.AuditService;
import com.campuscare.service.RiskAlertService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 风险预警接口：辅导员工作台。
 * SecurityConfig 中已限定 /api/risk/alerts/** 仅 COUNSELOR / ADMIN 可访问。
 */
@Tag(name = "03-风险预警", description = "预警列表、处置、统计（仅辅导员/管理员）")
@RestController
@RequestMapping("/api/risk/alerts")
@RequiredArgsConstructor
public class RiskAlertController {

    private final RiskAlertService riskAlertService;
    private final AuditService auditService;

    @Operation(summary = "预警分页列表", description = "status: PENDING/HANDLED；riskLevel: MEDIUM/HIGH，不传查全部")
    @GetMapping
    public Result<IPage<RiskAlert>> page(@RequestParam(defaultValue = "1") long current,
                                         @RequestParam(defaultValue = "10") long size,
                                         @RequestParam(required = false) String status,
                                         @RequestParam(required = false) String riskLevel) {
        return Result.ok(riskAlertService.page(current, size, status, riskLevel));
    }

    @Operation(summary = "处理预警", description = "填写处置备注，状态置为 HANDLED")
    @PostMapping("/{id}/handle")
    public Result<Void> handle(@PathVariable Long id,
                               @RequestBody(required = false) Map<String, String> body) {
        String remark = body == null ? null : body.get("remark");
        riskAlertService.handle(id, SecurityUtils.currentUserId(), remark);
        // 处置同样是不可逆动作：谁把这条工单关掉的，将来要能被追问。
        // 备注本身已存在工单上，这里不重复存，避免审计表被长文本撑爆。
        auditService.record(AuditService.HANDLE_ALERT, AuditService.TARGET_ALERT,
                id, "处置风险工单");
        return Result.ok();
    }

    @Operation(summary = "风险看板统计")
    @GetMapping("/statistics")
    public Result<Map<String, Object>> statistics() {
        return Result.ok(riskAlertService.statistics());
    }
}
