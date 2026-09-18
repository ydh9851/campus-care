package com.campuscare.controller;

import com.campuscare.common.Result;
import com.campuscare.entity.ConsultReport;
import com.campuscare.security.SecurityUtils;
import com.campuscare.service.ConsultReportService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

/**
 * 咨询报告接口
 */
@Tag(name = "04-咨询报告", description = "会话总结、情绪评分、干预建议")
@RestController
@RequestMapping("/api/report")
@RequiredArgsConstructor
public class ConsultReportController {

    private final ConsultReportService consultReportService;

    @Operation(summary = "生成咨询报告", description = "把整个会话交给 LLM 总结，重复调用会覆盖")
    @PostMapping("/{conversationId}")
    public Result<ConsultReport> generate(@PathVariable Long conversationId) {
        return Result.ok(consultReportService.generate(SecurityUtils.currentUserId(), conversationId));
    }

    @Operation(summary = "查看咨询报告")
    @GetMapping("/{conversationId}")
    public Result<ConsultReport> get(@PathVariable Long conversationId) {
        return Result.ok(consultReportService.get(SecurityUtils.currentUserId(), conversationId));
    }
}
