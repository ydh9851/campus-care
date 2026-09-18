package com.campuscare.service;

import com.campuscare.common.RiskLevel;
import com.campuscare.dto.Dashboard;
import com.campuscare.mapper.RiskAlertMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.sql.Timestamp;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 辅导员数据看板：把 SQL 聚合结果整理成图表结构，并从数字里提炼结论。
 * 全部是只读查询，因此不开事务。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DashboardService {

    private final RiskAlertMapper riskAlertMapper;

    /** 默认看近 14 天 */
    private static final int DEFAULT_DAYS = 14;
    /** 默认取 TOP 8 个学生 */
    private static final int DEFAULT_TOP = 8;
    /** 时段规律至少要有这么多次才值得下结论，避免用 2 条数据「发现规律」 */
    private static final int INSIGHT_MIN_SAMPLES = 3;

    public Dashboard build(int days, int topLimit) {
        int d = clamp(days, 3, 60);
        int t = clamp(topLimit, 3, 20);

        Dashboard dashboard = new Dashboard();
        List<Dashboard.HourPoint> hours = buildHours();
        Dashboard.PeakWindow peak = buildPeakWindow(hours);

        dashboard.setSummary(buildSummary());
        dashboard.setRiskDistribution(buildRiskDistribution());
        dashboard.setTrend(buildTrend(d));
        dashboard.setHours(hours);
        dashboard.setPeakWindow(peak);
        dashboard.setSourceDistribution(buildSourceDistribution());
        dashboard.setTopStudents(buildTopStudents(t));
        dashboard.setHandle(buildHandleEfficiency());
        dashboard.setInsights(buildInsights(dashboard, peak, d));

        log.info("生成数据看板: 近{}天, TOP{}", d, t);
        return dashboard;
    }

    // ============================================================
    // 各区块
    // ============================================================

    private Dashboard.Summary buildSummary() {
        Map<String, Object> row = riskAlertMapper.selectStatistics();
        Dashboard.Summary s = new Dashboard.Summary();
        s.setTotalCount(toInt(row.get("totalCount")));
        s.setHighCount(toInt(row.get("highCount")));
        s.setMediumCount(toInt(row.get("mediumCount")));
        s.setPendingCount(toInt(row.get("pendingCount")));
        s.setHandledCount(toInt(row.get("handledCount")));
        s.setStudentCount(toInt(row.get("studentCount")));
        s.setHighRatio(s.getTotalCount() == 0
                ? 0
                : Math.round(s.getHighCount() * 1000.0 / s.getTotalCount()) / 10.0);
        return s;
    }

    private List<Dashboard.NameValue> buildRiskDistribution() {
        Map<String, Object> row = riskAlertMapper.selectStatistics();
        List<Dashboard.NameValue> list = new ArrayList<>();
        list.add(new Dashboard.NameValue("HIGH", toInt(row.get("highCount"))));
        list.add(new Dashboard.NameValue("MEDIUM", toInt(row.get("mediumCount"))));
        return list;
    }

    private List<Dashboard.NameValue> buildSourceDistribution() {
        Map<String, Object> row = riskAlertMapper.selectStatistics();
        List<Dashboard.NameValue> list = new ArrayList<>();
        list.add(new Dashboard.NameValue("CHAT", toInt(row.get("chatCount"))));
        list.add(new Dashboard.NameValue("ASSESSMENT", toInt(row.get("assessmentCount"))));
        return list;
    }

    /**
     * 近 N 天趋势，按天补零。
     * GROUP BY 只返回有工单的日期，不补齐的话折线会把断点连成直线，看着像一直在增长。
     */
    private List<Dashboard.TrendPoint> buildTrend(int days) {
        Map<String, Dashboard.TrendPoint> byDay = new LinkedHashMap<>();
        LocalDate today = LocalDate.now();
        for (int i = days - 1; i >= 0; i--) {
            String key = today.minusDays(i).toString();
            Dashboard.TrendPoint point = new Dashboard.TrendPoint();
            point.setDay(key);
            byDay.put(key, point);
        }

        for (Map<String, Object> row : riskAlertMapper.selectTrendByDay(days)) {
            Dashboard.TrendPoint point = byDay.get(toStr(row.get("day")));
            if (point != null) {
                point.setTotal(toInt(row.get("total")));
                point.setHigh(toInt(row.get("high")));
            }
        }
        return new ArrayList<>(byDay.values());
    }

    /** 24 小时分布，补齐没有工单的小时（否则柱状图的 x 轴会缺格） */
    private List<Dashboard.HourPoint> buildHours() {
        Dashboard.HourPoint[] buckets = new Dashboard.HourPoint[24];
        for (int i = 0; i < 24; i++) {
            Dashboard.HourPoint p = new Dashboard.HourPoint();
            p.setHour(i);
            buckets[i] = p;
        }
        for (Map<String, Object> row : riskAlertMapper.selectDistributionByHour()) {
            int hour = toInt(row.get("hour"));
            if (hour >= 0 && hour < 24) {
                buckets[hour].setTotal(toInt(row.get("total")));
            }
        }
        return List.of(buckets);
    }

    private List<Dashboard.TopStudent> buildTopStudents(int limit) {
        List<Dashboard.TopStudent> list = new ArrayList<>();
        for (Map<String, Object> row : riskAlertMapper.selectTopStudents(limit)) {
            Dashboard.TopStudent stu = new Dashboard.TopStudent();
            stu.setUserId(row.get("userId") == null ? null : ((Number) row.get("userId")).longValue());
            stu.setRealName(toStr(row.get("realName")));
            stu.setStudentNo(toStr(row.get("studentNo")));
            stu.setAlertCount(toInt(row.get("alertCount")));
            stu.setHighCount(toInt(row.get("highCount")));
            stu.setPendingCount(toInt(row.get("pendingCount")));
            stu.setRiskLevel(weightToLevel(toInt(row.get("riskWeight"))));
            stu.setLastTime(toTime(row.get("lastTime")));
            list.add(stu);
        }
        return list;
    }

    private Dashboard.HandleEfficiency buildHandleEfficiency() {
        Map<String, Object> row = riskAlertMapper.selectHandleEfficiency();
        Dashboard.HandleEfficiency h = new Dashboard.HandleEfficiency();
        h.setHandledCount(toInt(row.get("handledCount")));
        Double avg = toDouble(row.get("avgMinutes"));
        h.setAvgMinutes(avg == null ? null : Math.round(avg * 10) / 10.0);
        return h;
    }

    /**
     * 找出工单最集中的连续 3 小时。
     * 窗口可能横跨 0 点（如 22:00-01:00），所以起点取遍 0~23 并用 % 24 回绕。
     * 样本不足 INSIGHT_MIN_SAMPLES 条时置 available=false，不给结论。
     */
    private Dashboard.PeakWindow buildPeakWindow(List<Dashboard.HourPoint> hours) {
        int[] counts = new int[24];
        int total = 0;
        for (Dashboard.HourPoint p : hours) {
            counts[p.getHour()] = p.getTotal();
            total += p.getTotal();
        }

        Dashboard.PeakWindow peak = new Dashboard.PeakWindow();
        peak.setAvailable(false);
        if (total < INSIGHT_MIN_SAMPLES) {
            return peak;
        }

        int bestStart = 0;
        int bestSum = -1;
        for (int start = 0; start < 24; start++) {
            int sum = counts[start] + counts[(start + 1) % 24] + counts[(start + 2) % 24];
            if (sum > bestSum) {
                bestSum = sum;
                bestStart = start;
            }
        }

        peak.setStartHour(bestStart);
        peak.setEndHour((bestStart + 3) % 24);
        peak.setCount(bestSum);
        peak.setRatio((int) Math.round(bestSum * 100.0 / total));
        peak.setAvailable(bestSum > 0);
        return peak;
    }

    /** 积压描述：0 天时说「今天产生的」，比「已积压 0 天」像人话 */
    private String backlogText() {
        LocalDateTime oldest = riskAlertMapper.selectOldestPendingTime();
        if (oldest == null) {
            return "";
        }
        long days = daysBetween(oldest);
        return days == 0 ? "，最早一条是今天产生的" : String.format("，最早一条已积压 %d 天", days);
    }

    // ============================================================
    // 结论提炼
    // ============================================================

    /** 把数字翻译成几句可直接读的判断 */
    private List<String> buildInsights(Dashboard d, Dashboard.PeakWindow peak, int days) {
        List<String> insights = new ArrayList<>();
        Dashboard.Summary s = d.getSummary();

        if (s.getTotalCount() == 0) {
            insights.add("暂无风险工单，系统运行正常。");
            return insights;
        }

        insights.add(String.format("累计 %d 条工单，涉及 %d 名学生，其中高危 %d 条（占 %s%%）。",
                s.getTotalCount(), s.getStudentCount(), s.getHighCount(), trimZero(s.getHighRatio())));

        if (s.getPendingCount() > 0) {
            insights.add(String.format("当前有 %d 条待处理%s，建议优先清理高危件。",
                    s.getPendingCount(), backlogText()));
        } else {
            insights.add("所有工单均已处置，无积压。");
        }

        if (peak.isAvailable()) {
            insights.add(String.format("工单集中在 %02d:00–%02d:00（占 %d%%），%s是重点关注时段。",
                    peak.getStartHour(), peak.getEndHour(), peak.getRatio(),
                    periodLabel(peak.getStartHour())));
        }

        Dashboard.HandleEfficiency h = d.getHandle();
        if (h.getHandledCount() > 0 && h.getAvgMinutes() != null) {
            insights.add(String.format("已处置 %d 条，平均处置时长 %s 分钟。",
                    h.getHandledCount(), trimZero(h.getAvgMinutes())));
        }

        if (!d.getTopStudents().isEmpty()) {
            Dashboard.TopStudent top = d.getTopStudents().get(0);
            if (top.getHighCount() > 0) {
                insights.add(String.format("最需关注：%s（%s 条工单，其中高危 %d 条）。",
                        displayName(top), top.getAlertCount(), top.getHighCount()));
            }
        }

        insights.add(String.format("以上趋势统计基于近 %d 天数据。", days));
        return insights;
    }

    private String displayName(Dashboard.TopStudent s) {
        if (s.getRealName() != null && !s.getRealName().isBlank()) {
            return s.getStudentNo() == null ? s.getRealName() : s.getRealName() + " " + s.getStudentNo();
        }
        return "学生 " + s.getUserId();
    }

    // ============================================================
    // 工具方法
    // ============================================================

    /**
     * 聚合结果放进 Map 时类型不固定：COUNT 给 Long，SUM 给 BigDecimal，空结果给 null，
     * 直接强转会抛 ClassCastException，统一走这里转换。
     */
    private static int toInt(Object value) {
        if (value == null) {
            return 0;
        }
        if (value instanceof Number n) {
            return n.intValue();
        }
        try {
            return Integer.parseInt(value.toString());
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private static Double toDouble(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number n) {
            return n.doubleValue();
        }
        try {
            return Double.parseDouble(value.toString());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static String toStr(Object value) {
        return value == null ? null : value.toString();
    }

    /** DATETIME 取回来可能是 LocalDateTime 或 Timestamp（取决于驱动版本），两种都兜住 */
    private static LocalDateTime toTime(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof LocalDateTime ldt) {
            return ldt;
        }
        if (value instanceof Timestamp ts) {
            return ts.toLocalDateTime();
        }
        if (value instanceof java.util.Date date) {
            return LocalDateTime.ofInstant(date.toInstant(), ZoneId.systemDefault());
        }
        return null;
    }

    /** 时段中文名，跟着高峰窗口的起始小时走，不要在文案里写死「深夜」 */
    private static String periodLabel(int hour) {
        if (hour < 5) {
            return "凌晨";
        }
        if (hour < 8) {
            return "清晨";
        }
        if (hour < 11) {
            return "上午";
        }
        if (hour < 13) {
            return "午间";
        }
        if (hour < 17) {
            return "午后";
        }
        if (hour < 19) {
            return "傍晚";
        }
        return hour < 23 ? "晚间" : "深夜";
    }

    private static String weightToLevel(int weight) {
        if (weight >= 3) {
            return RiskLevel.HIGH.name();
        }
        return weight == 2 ? "MEDIUM" : RiskLevel.LOW.name();
    }

    private static long daysBetween(LocalDateTime from) {
        return Math.max(0, Duration.between(from, LocalDateTime.now()).toDays());
    }

    private static int clamp(int value, int min, int max) {
        return Math.min(Math.max(value, min), max);
    }

    /** 12.0 → "12"、12.5 → "12.5"，避免结论里出现一堆 ".0" */
    private static String trimZero(Number n) {
        double d = n.doubleValue();
        return d == Math.floor(d) ? String.valueOf((long) d) : String.valueOf(d);
    }
}
