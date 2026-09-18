package com.campuscare.controller;

import com.campuscare.common.Result;
import com.campuscare.dto.AssessmentResult;
import com.campuscare.dto.ScaleDetail;
import com.campuscare.dto.SubmitAssessmentRequest;
import com.campuscare.entity.AssessmentRecord;
import com.campuscare.security.SecurityUtils;
import com.campuscare.service.AssessmentService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 心理测评接口：标准量表作答与结果查询。
 *
 * 量表定义放在 resources/scales/*.json，接口把题目和选项原样给前端，
 * 前端按定义渲染 —— 加一份新量表不需要改前端代码。
 */
@Tag(name = "05-心理测评", description = "标准量表作答、计分与风险联动")
@RestController
@RequestMapping("/api/assessment")
@RequiredArgsConstructor
public class AssessmentController {

    private final AssessmentService assessmentService;

    @Operation(summary = "量表列表", description = "返回可用量表的摘要信息（不含题目）")
    @GetMapping("/scales")
    public Result<List<Map<String, Object>>> scales() {
        return Result.ok(assessmentService.listScales());
    }

    @Operation(summary = "量表详情", description = "返回题目、选项与分级规则，前端据此渲染答题界面")
    @GetMapping("/scales/{code}")
    public Result<ScaleDetail> scale(@PathVariable String code) {
        return Result.ok(assessmentService.getScale(code));
    }

    @Operation(summary = "提交测评",
            description = "服务端计分；命中单题高危规则或总分达到门槛时，会自动生成风险工单进入统一工单池")
    @PostMapping("/submit")
    public Result<AssessmentResult> submit(@Valid @RequestBody SubmitAssessmentRequest request) {
        return Result.ok(assessmentService.submit(SecurityUtils.currentUserId(), request));
    }

    @Operation(summary = "我的测评记录")
    @GetMapping("/records")
    public Result<List<AssessmentRecord>> records() {
        return Result.ok(assessmentService.myRecords(SecurityUtils.currentUserId()));
    }
}
