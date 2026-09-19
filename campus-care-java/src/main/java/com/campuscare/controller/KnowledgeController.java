package com.campuscare.controller;

import com.campuscare.common.Result;
import com.campuscare.dto.KnowledgeCategory;
import com.campuscare.dto.KnowledgeItem;
import com.campuscare.service.KnowledgeService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 心理科普接口。
 *
 * 语料实际存放在 Python 侧（与 RAG 检索共用同一份 psych_faq.json），
 * 这里只做代理与过滤，好处是前端只需要认 Java 一个入口。
 */
@Tag(name = "08-心理科普", description = "知识库浏览，语料与 RAG 检索共用同一份")
@RestController
@RequestMapping("/api/knowledge")
@RequiredArgsConstructor
public class KnowledgeController {

    private final KnowledgeService knowledgeService;

    @Operation(summary = "知识库条目列表", description = "category 与 q 均为空时返回全部")
    @GetMapping
    public Result<List<KnowledgeItem>> list(
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String q) {
        return Result.ok(knowledgeService.list(category, q));
    }

    @Operation(summary = "知识库分类与条数")
    @GetMapping("/categories")
    public Result<List<KnowledgeCategory>> categories() {
        return Result.ok(knowledgeService.categories());
    }
}
