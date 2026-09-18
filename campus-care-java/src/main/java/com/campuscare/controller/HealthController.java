package com.campuscare.controller;

import com.campuscare.client.PythonAgentClient;
import com.campuscare.common.Result;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 健康检查：一眼看出 Java 服务和 Python AI 服务是否都活着。
 * 白名单接口，不需要登录。
 */
@Tag(name = "00-健康检查")
@RestController
@RequestMapping("/api/health")
@RequiredArgsConstructor
public class HealthController {

    private final PythonAgentClient pythonAgentClient;

    @Operation(summary = "服务健康检查", description = "返回 Java 状态 + Python AI 服务是否在线")
    @GetMapping
    public Result<Map<String, Object>> health() {
        boolean pythonOnline = pythonAgentClient.ping();

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("service", "campus-care-java");
        data.put("status", "UP");
        data.put("time", LocalDateTime.now().toString());
        data.put("pythonAi", pythonOnline ? "ONLINE" : "OFFLINE");
        return Result.ok(data);
    }
}
