package com.campuscare.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

import java.util.List;

/**
 * Java → Python 的请求体（两个服务之间的内部协议）。
 */
@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class AgentChatRequest {

    private Long userId;

    private Long conversationId;

    /** 学生本次说的话 */
    private String message;

    /** 最近 N 轮历史，供 LLM 保持上下文 */
    private List<HistoryMessage> history;

    /** 链路追踪 id：Java 侧生成后透传，Python 回显，两端日志用同一个 id 串起来 */
    private String traceId;
}
