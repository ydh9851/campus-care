package com.campuscare.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

import java.util.List;

/**
 * Python → Java 的响应体（data 部分）。
 */
@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentChatResponse {

    /** AI 回复正文 */
    private String reply;

    /** 意图识别 Agent 的结论 */
    private String intent;

    /** 风险预警 Agent 的结论 LOW / MEDIUM / HIGH */
    private String riskLevel;

    /** 命中的风险关键词 */
    private List<String> keywords;

    /** 风险处置建议（高危时使用） */
    private String aiSuggestion;

    /** RAG 命中的 FAQ 来源 */
    private List<String> ragSources;

    /** 消耗 token */
    private Integer tokens;
}
