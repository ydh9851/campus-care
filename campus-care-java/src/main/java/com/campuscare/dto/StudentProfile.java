package com.campuscare.dto;

import com.campuscare.entity.AssessmentRecord;
import com.campuscare.entity.ConsultReport;
import com.campuscare.entity.Conversation;
import com.campuscare.entity.RiskAlert;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 学生心理档案（一生一档），是对已有数据的聚合视图，没有对应新表。
 * 单独做聚合层是为了让「最高风险」「最近活动时间」这类跨表结论口径一致，
 * 同时档案页只需一次请求。
 */
@Data
public class StudentProfile {

    /** 基本信息 */
    private Basic basic;

    /** 汇总概览（档案页顶部的数字卡） */
    private Overview overview;

    /** 咨询会话（倒序） */
    private List<Conversation> conversations;

    /** 测评记录（倒序） */
    private List<AssessmentRecord> assessments;

    /** 风险工单（倒序，对话与量表来源混在一起 —— 它们本就是同一个工单池） */
    private List<RiskAlert> alerts;

    /** 咨询报告（倒序，情绪趋势的数据来源） */
    private List<ConsultReport> reports;

    /** 统一时间线：把工单 / 测评 / 报告按时间倒序揉成一条，最多返回前 20 条 */
    private List<TimelineItem> timeline;

    @Data
    public static class Basic {
        private Long userId;
        private String username;
        private String realName;
        private String studentNo;
        private String phone;
        private String email;
        private String role;
        private LocalDateTime registerTime;
    }

    @Data
    public static class Overview {
        private int conversationCount;
        /** 累计对话轮次（各会话 turnCount 之和） */
        private int totalTurns;
        private int alertCount;
        private int pendingAlertCount;
        private int highAlertCount;
        private int assessmentCount;
        /** 已覆盖的量表种类数，用来判断「是否做过全面筛查」 */
        private int coveredScaleCount;
        /** 综合最高风险：会话 / 工单 / 测评三处取最高 */
        private String highestRiskLevel;
        /** 最近一次咨询报告的情绪评分，没有报告时为 null */
        private Integer latestEmotionScore;
        private LocalDateTime lastActiveTime;
    }

    @Data
    public static class TimelineItem {
        /** ALERT（风险工单） / ASSESSMENT（量表测评） / REPORT（咨询报告） */
        private String type;
        private String title;
        private String detail;
        private String riskLevel;
        private LocalDateTime time;
    }
}
