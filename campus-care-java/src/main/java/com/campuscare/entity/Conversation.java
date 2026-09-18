package com.campuscare.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 咨询会话表：一次连续对话 = 一条 conversation
 */
@Data
@TableName("conversation")
public class Conversation implements Serializable {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 所属学生 id */
    private Long userId;

    /** 会话标题，取首条消息前 20 字 */
    private String title;

    /** 会话内出现过的最高风险等级 LOW / MEDIUM / HIGH */
    private String riskLevel;

    /**
     * 对话轮次（1 轮 = 学生 1 条 + AI 1 条），不是 message 表的行数。
     * 冗余存储，避免列表页每次都去 message 表 COUNT(*)。
     */
    private Integer turnCount;

    /** 1 进行中 0 已结束 */
    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
