package com.campuscare.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 消息表：一问一答都落这里，AI 回复会带上意图和风险等级
 */
@Data
@TableName("message")
public class Message implements Serializable {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long conversationId;

    private Long userId;

    /** user：学生说的；assistant：AI 回复的 */
    private String role;

    private String content;

    /** PSYCH_EMOTION 心理倾诉 / KNOWLEDGE_QUERY 知识查询 / RISK_ALERT 高危预警 / CHITCHAT 闲聊 */
    private String intent;

    /** 本条消息的风险等级 LOW / MEDIUM / HIGH */
    private String riskLevel;

    /** 消耗 token 数，统计用 */
    private Integer tokens;

    private LocalDateTime createTime;
}
