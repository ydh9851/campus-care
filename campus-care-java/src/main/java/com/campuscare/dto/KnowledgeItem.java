package com.campuscare.dto;

import lombok.Data;

/**
 * 知识库条目（心理科普）。
 * 字段与 Python 侧 data/psych_faq.json 一一对应。
 */
@Data
public class KnowledgeItem {
    private String id;
    private String category;
    private String title;
    private String content;
    private String source;
}
