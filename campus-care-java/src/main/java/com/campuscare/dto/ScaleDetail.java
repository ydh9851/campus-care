package com.campuscare.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

import java.util.List;

/**
 * 量表定义（从 resources/scales/*.json 加载）。
 * 采用数据驱动：换量表、改阈值、加高危题都不需要改代码，
 * 新增一份量表只需放入 json，前端拿到 questions / options / levels 即可渲染。
 */
@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class ScaleDetail {

    private String code;
    private String name;
    private String intro;
    private String note;
    private Integer maxScore;

    private List<Option> options;
    private List<Question> questions;
    private List<Level> levels;

    /** 单题高危规则：命中就单独判高危，不参与总分分级 */
    private List<CriticalItem> criticalItems;

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Option {
        private Integer value;
        private String label;
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Question {
        private Integer no;
        private String text;
        private Boolean critical;
    }

    /** 总分区间 -> 严重程度 + 风险等级 */
    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Level {
        private Integer max;
        private String severity;
        private String label;
        private String riskLevel;
    }

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class CriticalItem {
        private Integer no;
        private Integer minScore;
        private String riskLevel;
        private String note;
    }
}
