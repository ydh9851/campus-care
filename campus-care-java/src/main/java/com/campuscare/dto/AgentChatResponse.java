package com.campuscare.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

import java.util.List;
import java.util.Map;

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

    // ---------- 可观测性与合规（Python 侧返回，Java 透传给前端） ----------

    /** 链路追踪 id */
    private String traceId;

    /** 本次使用的检索模式 hybrid / vector */
    private String retrievalMode;

    /** 各 prompt 的版本号（prompt 名 -> 内容哈希前 8 位），便于回溯线上用的是哪一版文案 */
    private Map<String, String> promptVersion;

    /** 免责声明：AI 回复不构成医学诊断 */
    private String disclaimer;

    /** 是否需要转人工（高危会话为 true） */
    private Boolean needHandoff;
}
