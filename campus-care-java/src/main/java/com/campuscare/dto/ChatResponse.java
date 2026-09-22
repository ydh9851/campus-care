package com.campuscare.dto;

import lombok.Data;

import java.util.List;
import java.util.Map;

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

    /** 链路追踪 id：出问题时拿它去两边日志里搜同一条链路 */
    private String traceId;

    /** 本次检索模式 hybrid（BM25+向量融合）/ vector */
    private String retrievalMode;

    /** 各 prompt 版本号，便于回溯 */
    private Map<String, String> promptVersion;

    /** 免责声明，由前端决定展示位置 */
    private String disclaimer;

    /** 是否需要转人工，高危会话为 true，前端可据此给出人工入口 */
    private Boolean needHandoff;
}
