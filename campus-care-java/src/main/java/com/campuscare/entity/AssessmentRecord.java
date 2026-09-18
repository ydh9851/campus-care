package com.campuscare.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 心理测评记录：学生做完一份标准量表后的一次作答结果。
 *
 * 与对话风险的区别：
 *   对话风险是「AI 从自然语言里推测」出来的，偏召回；
 *   量表结果是「按标准计分规则算」出来的，偏精确。
 *   两者进同一个工单池（risk_alert），辅导员一屏看完所有来源。
 */
@Data
@TableName("assessment_record")
public class AssessmentRecord implements Serializable {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    /** 量表编码：PHQ9 / GAD7 */
    private String scaleCode;

    /** 量表名称（冗余一份，列表页就不用再回查量表定义） */
    private String scaleName;

    private Integer totalScore;

    /** 严重程度编码：NONE/MILD/MODERATE/MODERATELY_SEVERE/SEVERE */
    private String severity;

    /** 严重程度中文，如「中度抑郁」 */
    private String severityLabel;

    /** 换算出的风险等级：LOW/MEDIUM/HIGH */
    private String riskLevel;

    /** 答题明细：逗号分隔的选项分值，如 "1,2,0,3,..." */
    private String answers;

    /** 触发高危判定的题号，如 "9"；没有则为 null */
    private String highRiskItems;

    private LocalDateTime createTime;
}
