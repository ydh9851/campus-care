package com.campuscare.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 辅导员数据看板。
 *
 * 和 StudentProfile（单个人）相对：这里是全局视角。
 *
 * 字段形状是「贴近图表但仍是业务语义」的折中：
 *   - riskDistribution / sourceDistribution 用 [{name, value}]，饼图/环形图原样能画；
 *   - trend / hours 用对象数组而不是平行数组，避免前端按下标对齐出错。
 * 没有直接输出 ECharts 的 option —— 那会让后端依赖具体图表库，
 * 换图表库（或加一个新的 App 端）就得改后端。
 */
@Data
public class Dashboard {

    private Summary summary;

    /** 风险等级分布（环形图） */
    private List<NameValue> riskDistribution;

    /** 近 N 天趋势，已补零成连续日期 */
    private List<TrendPoint> trend;

    /** 24 小时时段分布，长度恒为 24 */
    private List<HourPoint> hours;

    /** 来源分布（对话 / 量表） */
    private List<NameValue> sourceDistribution;

    /** 最需要关注的学生 */
    private List<TopStudent> topStudents;

    /** 处置效率 */
    private HandleEfficiency handle;

    /**
     * 工单最集中的 3 小时窗口（跨 0 点会回绕，例如 22:00-01:00）。
     * 前端用它对柱状图做高亮。单独给字段而不是让前端解析 insights 文案，
     * 避免文案调整导致前端静默失效。
     */
    private PeakWindow peakWindow;

    /** 自动生成的中文结论 —— 看板不该只给图，还要直接给话 */
    private List<String> insights;

    @Data
    public static class Summary {
        private int totalCount;
        private int highCount;
        private int mediumCount;
        private int pendingCount;
        private int handledCount;
        private int studentCount;
        /** 高危占比（0~100，保留一位小数） */
        private double highRatio;
    }

    @Data
    public static class NameValue {
        private String name;
        private Integer value;

        public NameValue(String name, Integer value) {
            this.name = name;
            this.value = value;
        }
    }

    @Data
    public static class TrendPoint {
        private String day;
        private int total;
        private int high;
    }

    @Data
    public static class HourPoint {
        private int hour;
        private int total;
    }

    @Data
    public static class TopStudent {
        private Long userId;
        private String realName;
        private String studentNo;
        private int alertCount;
        private int highCount;
        private int pendingCount;
        private String riskLevel;
        /** 时间格式由全局 JacksonConfig 统一处理，这里不用再标 @JsonFormat */
        private LocalDateTime lastTime;
    }

    @Data
    public static class HandleEfficiency {
        private int handledCount;
        /** 平均处理时长（分钟），没有已处理工单时为 null */
        private Double avgMinutes;
    }

    @Data
    public static class PeakWindow {
        private int startHour;
        private int endHour;
        private int count;
        /** 占全天工单的百分比 */
        private int ratio;
        /** 样本太少时置 false，前端不做高亮、也不下结论 */
        private boolean available;
    }
}
