package com.campuscare.dto;

import lombok.AllArgsConstructor;
import lombok.Data;

/** 知识库分类及条数，供前端渲染筛选标签 */
@Data
@AllArgsConstructor
public class KnowledgeCategory {
    private String name;
    private int count;
}
