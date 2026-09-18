package com.campuscare.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.campuscare.common.BizException;
import com.campuscare.common.RiskLevel;
import com.campuscare.dto.StudentProfile;
import com.campuscare.entity.AssessmentRecord;
import com.campuscare.entity.ConsultReport;
import com.campuscare.entity.Conversation;
import com.campuscare.entity.RiskAlert;
import com.campuscare.entity.User;
import com.campuscare.mapper.AssessmentRecordMapper;
import com.campuscare.mapper.ConsultReportMapper;
import com.campuscare.mapper.ConversationMapper;
import com.campuscare.mapper.RiskAlertMapper;
import com.campuscare.mapper.UserMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 学生心理档案：把散落在 4 张表里的学生数据聚合成一份「一生一档」。
 * 不引入新表，档案只是同一份数据的另一种视角。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ProfileService {

    private final UserMapper userMapper;
    private final ConversationMapper conversationMapper;
    private final AssessmentRecordMapper assessmentRecordMapper;
    private final RiskAlertMapper riskAlertMapper;
    private final ConsultReportMapper consultReportMapper;

    /** 时间线最多返回多少条，避免档案页被长列表刷屏 */
    private static final int TIMELINE_LIMIT = 20;

    /** 详情字符串截断长度 */
    private static final int DETAIL_MAX = 60;

    public StudentProfile build(Long userId) {
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BizException("用户不存在");
        }

        // 一次性取出四类数据。单个学生的数据量很小，直接在内存里统计，口径也统一；
        // 若单学生数据涨到上万条，再改成 SQL 聚合 + 分页。
        List<Conversation> conversations = conversationMapper.selectList(
                Wrappers.<Conversation>lambdaQuery()
                        .eq(Conversation::getUserId, userId)
                        .orderByDesc(Conversation::getId));

        List<AssessmentRecord> assessments = assessmentRecordMapper.selectList(
                Wrappers.<AssessmentRecord>lambdaQuery()
                        .eq(AssessmentRecord::getUserId, userId)
                        .orderByDesc(AssessmentRecord::getId));

        List<RiskAlert> alerts = riskAlertMapper.selectList(
                Wrappers.<RiskAlert>lambdaQuery()
                        .eq(RiskAlert::getUserId, userId)
                        .orderByDesc(RiskAlert::getId));

        List<ConsultReport> reports = consultReportMapper.selectList(
                Wrappers.<ConsultReport>lambdaQuery()
                        .eq(ConsultReport::getUserId, userId)
                        .orderByDesc(ConsultReport::getId));

        StudentProfile profile = new StudentProfile();
        profile.setBasic(toBasic(user));
        profile.setConversations(conversations);
        profile.setAssessments(assessments);
        profile.setAlerts(alerts);
        profile.setReports(reports);
        profile.setOverview(buildOverview(conversations, assessments, alerts, reports));
        profile.setTimeline(buildTimeline(alerts, assessments, reports));

        log.info("生成学生档案: userId={}, 会话{} 测评{} 工单{} 报告{}",
                userId, conversations.size(), assessments.size(), alerts.size(), reports.size());
        return profile;
    }

    // ============================================================
    // 内部方法
    // ============================================================

    private StudentProfile.Basic toBasic(User user) {
        StudentProfile.Basic basic = new StudentProfile.Basic();
        basic.setUserId(user.getId());
        basic.setUsername(user.getUsername());
        basic.setRealName(user.getRealName());
        basic.setStudentNo(user.getStudentNo());
        basic.setPhone(user.getPhone());
        basic.setEmail(user.getEmail());
        basic.setRole(user.getRole());
        basic.setRegisterTime(user.getCreateTime());
        // 用 Basic 承载返回而不是直接返回 User 实体，从类型上杜绝 password 泄漏
        return basic;
    }

    private StudentProfile.Overview buildOverview(List<Conversation> conversations,
                                                  List<AssessmentRecord> assessments,
                                                  List<RiskAlert> alerts,
                                                  List<ConsultReport> reports) {
        StudentProfile.Overview overview = new StudentProfile.Overview();
        overview.setConversationCount(conversations.size());
        overview.setTotalTurns(conversations.stream()
                .mapToInt(c -> c.getTurnCount() == null ? 0 : c.getTurnCount())
                .sum());
        overview.setAlertCount(alerts.size());
        overview.setPendingAlertCount((int) alerts.stream()
                .filter(a -> "PENDING".equals(a.getStatus())).count());
        overview.setHighAlertCount((int) alerts.stream()
                .filter(a -> RiskLevel.HIGH.name().equals(a.getRiskLevel())).count());
        overview.setAssessmentCount(assessments.size());
        overview.setCoveredScaleCount((int) assessments.stream()
                .map(AssessmentRecord::getScaleCode).distinct().count());
        overview.setLatestEmotionScore(reports.isEmpty() ? null : reports.get(0).getEmotionScore());

        // 综合最高风险：会话、工单、测评三处分别取最高再取最大值。
        // 会话只反映聊出来的，测评只反映量表算出来的，只看一处会漏。
        RiskLevel highest = RiskLevel.LOW;
        for (Conversation c : conversations) {
            highest = RiskLevel.max(highest, RiskLevel.of(c.getRiskLevel()));
        }
        for (RiskAlert a : alerts) {
            highest = RiskLevel.max(highest, RiskLevel.of(a.getRiskLevel()));
        }
        for (AssessmentRecord r : assessments) {
            highest = RiskLevel.max(highest, RiskLevel.of(r.getRiskLevel()));
        }
        overview.setHighestRiskLevel(highest.name());

        // 最近活动时间 = 所有事件里最新的那个
        LocalDateTime last = null;
        for (Conversation c : conversations) {
            last = later(last, c.getUpdateTime());
        }
        for (RiskAlert a : alerts) {
            last = later(last, a.getCreateTime());
        }
        for (AssessmentRecord r : assessments) {
            last = later(last, r.getCreateTime());
        }
        for (ConsultReport r : reports) {
            last = later(last, r.getCreateTime());
        }
        overview.setLastActiveTime(last);
        return overview;
    }

    /**
     * 把工单、测评、报告揉成一条时间线。
     * 不放普通会话：健谈的学生会把真正的高危事件挤出屏幕，时间线要的是摘要不是日志。
     */
    private List<StudentProfile.TimelineItem> buildTimeline(List<RiskAlert> alerts,
                                                            List<AssessmentRecord> assessments,
                                                            List<ConsultReport> reports) {
        List<StudentProfile.TimelineItem> items = new ArrayList<>();

        for (RiskAlert a : alerts) {
            items.add(item(
                    "ALERT",
                    RiskAlertService.SOURCE_ASSESSMENT.equals(a.getSource()) ? "量表预警工单" : "对话预警工单",
                    a.getContent(),
                    a.getRiskLevel(),
                    a.getCreateTime()));
        }
        for (AssessmentRecord r : assessments) {
            items.add(item(
                    "ASSESSMENT",
                    r.getScaleName(),
                    r.getSeverityLabel() + "，总分 " + r.getTotalScore()
                            + (r.getHighRiskItems() == null ? "" : "，第 " + r.getHighRiskItems() + " 题涉及自伤念头"),
                    r.getRiskLevel(),
                    r.getCreateTime()));
        }
        for (ConsultReport r : reports) {
            items.add(item(
                    "REPORT",
                    "咨询报告",
                    "情绪评分 " + r.getEmotionScore() + " · " + truncate(r.getSummary(), DETAIL_MAX),
                    r.getRiskLevel(),
                    r.getCreateTime()));
        }

        // 时间倒序；time 为 null 的排在最后（避免脏数据把排序搞乱）
        items.sort((x, y) -> {
            if (x.getTime() == null && y.getTime() == null) {
                return 0;
            }
            if (x.getTime() == null) {
                return 1;
            }
            if (y.getTime() == null) {
                return -1;
            }
            return y.getTime().compareTo(x.getTime());
        });

        return items.size() > TIMELINE_LIMIT ? new ArrayList<>(items.subList(0, TIMELINE_LIMIT)) : items;
    }

    private StudentProfile.TimelineItem item(String type, String title, String detail,
                                             String riskLevel, LocalDateTime time) {
        StudentProfile.TimelineItem item = new StudentProfile.TimelineItem();
        item.setType(type);
        item.setTitle(title);
        item.setDetail(truncate(detail, DETAIL_MAX));
        item.setRiskLevel(riskLevel);
        item.setTime(time);
        return item;
    }

    private LocalDateTime later(LocalDateTime a, LocalDateTime b) {
        if (a == null) {
            return b;
        }
        if (b == null) {
            return a;
        }
        return a.isAfter(b) ? a : b;
    }

    private String truncate(String text, int max) {
        if (text == null) {
            return "";
        }
        return text.length() <= max ? text : text.substring(0, max) + "…";
    }
}
