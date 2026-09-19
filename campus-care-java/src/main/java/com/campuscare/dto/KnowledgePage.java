package com.campuscare.dto;

import lombok.Data;

import java.util.List;

/** Python /api/agent/kb/list 的返回结构 */
@Data
public class KnowledgePage {
    private int total;
    private List<KnowledgeItem> items;
}
