package com.campuscare.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 风险工单表（统一工单池）。
 * 对话预警和量表预警共用一张表，用 source 区分来源，让辅导员一屏看到所有待办。
 * 代价是量表来源的 conversation_id / message_id 必须允许为空。
 */
@Data
@TableName("risk_alert")
public class RiskAlert implements Serializable {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 来源：CHAT 对话预警 / ASSESSMENT 量表测评预警 */
    private String source;

    /** 关联会话（量表来源为 null） */
    private Long conversationId;

    /** 触发预警的那条消息 id（量表来源为 null） */
    private Long messageId;

    /** 关联的测评记录 id（对话来源为 null） */
    private Long assessmentRecordId;

    /** 涉及学生 */
    private Long userId;

    /** MEDIUM / HIGH */
    private String riskLevel;

    /** 命中的关键词或高危题号，逗号分隔 */
    private String keywords;

    /** 触发预警的原文（对话原话 / 量表结论） */
    private String content;

    /** AI 或规则生成的处置建议 */
    private String aiSuggestion;

    /** PENDING 待处理 / HANDLED 已处理 / CLOSED 已关闭 */
    private String status;

    /** 处理人（辅导员）id */
    private Long handlerId;

    private String handleRemark;

    private LocalDateTime createTime;

    private LocalDateTime handleTime;
}
