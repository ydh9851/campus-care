package com.campuscare.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 咨询报告表：会话结束后由 Python 侧 LLM 汇总生成，一个会话一份。
 */
@Data
@TableName("consult_report")
public class ConsultReport implements Serializable {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long conversationId;

    private Long userId;

    /** 对话摘要 */
    private String summary;

    /** 情绪评分 0-100，越高越积极 */
    private Integer emotionScore;

    /** 综合风险等级 */
    private String riskLevel;

    /** 干预建议 */
    private String suggestion;

    private LocalDateTime createTime;
}
