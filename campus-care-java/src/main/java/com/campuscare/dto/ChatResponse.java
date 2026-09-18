package com.campuscare.dto;

import lombok.Data;

import java.util.List;

/**
 * 咨询返回：AI 回复 + 意图 + 风险 + 检索来源，前端可直接渲染
 */
@Data
public class ChatResponse {

    private Long conversationId;

    /** AI 的回复正文 */
    private String reply;

    /** 识别出的意图 */
    private String intent;

    /** 本条消息风险等级 LOW / MEDIUM / HIGH */
    private String riskLevel;

    /** 命中风险关键词时生成的预警 id，前端可提示"已通知辅导员" */
    private Long alertId;

    /** RAG 检索命中的 FAQ 来源标题 */
    private List<String> ragSources;

    /** 本次消耗 token */
    private Integer tokens;
}
