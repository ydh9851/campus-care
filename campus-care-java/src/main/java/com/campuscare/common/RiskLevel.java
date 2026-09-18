package com.campuscare.common;

/**
 * 风险等级枚举。带严重度排序，用于比较两次风险的轻重。
 */
public enum RiskLevel {

    /** 低风险 */
    LOW(0),

    /** 中风险：情绪问题倾向，需要关注 */
    MEDIUM(1),

    /** 高风险：自杀 / 自残倾向，必须立即人工干预 */
    HIGH(2);

    private final int severity;

    RiskLevel(int severity) {
        this.severity = severity;
    }

    public int getSeverity() {
        return severity;
    }

    /** 字符串转枚举，非法值一律按 LOW 处理，避免脏数据导致 NPE */
    public static RiskLevel of(String value) {
        if (value == null || value.isBlank()) {
            return LOW;
        }
        try {
            return valueOf(value.trim().toUpperCase());
        } catch (IllegalArgumentException e) {
            return LOW;
        }
    }

    /** 取两者中更严重的 */
    public static RiskLevel max(RiskLevel a, RiskLevel b) {
        if (a == null) {
            return b == null ? LOW : b;
        }
        if (b == null) {
            return a;
        }
        return a.severity >= b.severity ? a : b;
    }

    public boolean isDangerous() {
        return this != LOW;
    }

    /** 是否达到需要落库预警的程度 */
    public boolean needAlert() {
        return this == MEDIUM || this == HIGH;
    }
}
