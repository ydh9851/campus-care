package com.campuscare.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.campuscare.entity.RiskAlert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 风险预警 Mapper
 */
@Mapper
public interface RiskAlertMapper extends BaseMapper<RiskAlert> {

    /**
     * 风险统计。用 SUM(CASE WHEN) 一次扫描算出所有指标，省掉多次 COUNT 往返。
     * 无数据时 SUM 返回 null 而非 0，调用方需按 0 兜底。
     */
    @Select("""
            SELECT
              SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END)   AS highCount,
              SUM(CASE WHEN risk_level = 'MEDIUM' THEN 1 ELSE 0 END) AS mediumCount,
              SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END)    AS pendingCount,
              SUM(CASE WHEN status = 'HANDLED' THEN 1 ELSE 0 END)    AS handledCount,
              SUM(CASE WHEN source = 'CHAT' THEN 1 ELSE 0 END)       AS chatCount,
              SUM(CASE WHEN source = 'ASSESSMENT' THEN 1 ELSE 0 END) AS assessmentCount,
              COUNT(*)                                               AS totalCount,
              COUNT(DISTINCT user_id)                                AS studentCount
            FROM risk_alert
            """)
    Map<String, Object> selectStatistics();

    /** 某学生待处理预警数（登录时提示辅导员） */
    @Select("SELECT COUNT(*) FROM risk_alert WHERE user_id = #{userId} AND status = 'PENDING'")
    long countPendingByUser(@Param("userId") Long userId);

    // ---------- 数据看板聚合查询 ----------
    // 一律用 SQL 聚合而不是捞进内存分组：工单量随使用时间增长，
    // 全量捞回来会让「打开看板」的开销无限增长，GROUP BY 只传回几十行。

    /**
     * 近 N 天工单趋势（按天聚合）。
     * DATE_FORMAT 让日期以字符串返回，避免 java.sql.Date 的时区歧义。
     * 没有工单的日期不会出现在结果里，补零由 Service 层处理。
     */
    @Select("""
            SELECT DATE_FORMAT(create_time, '%Y-%m-%d')                  AS day,
                   COUNT(*)                                              AS total,
                   SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END)  AS high
            FROM risk_alert
            WHERE create_time >= DATE_SUB(CURDATE(), INTERVAL #{days} DAY)
            GROUP BY DATE_FORMAT(create_time, '%Y-%m-%d')
            ORDER BY day
            """)
    List<Map<String, Object>> selectTrendByDay(@Param("days") int days);

    /** 工单时段分布（0~23 点） */
    @Select("""
            SELECT HOUR(create_time) AS hour, COUNT(*) AS total
            FROM risk_alert
            GROUP BY HOUR(create_time)
            ORDER BY hour
            """)
    List<Map<String, Object>> selectDistributionByHour();

    /**
     * 最需要关注的学生（按高危数排序）。
     * 注意不能写 MAX(risk_level)：字符串字典序是 HIGH &lt; LOW &lt; MEDIUM，
     * {MEDIUM, HIGH} 取 MAX 会得到 MEDIUM，把高危算成中危，必须先映射成权重。
     */
    @Select("""
            SELECT a.user_id        AS userId,
                   u.real_name      AS realName,
                   u.student_no     AS studentNo,
                   COUNT(*)         AS alertCount,
                   SUM(CASE WHEN a.risk_level = 'HIGH' THEN 1 ELSE 0 END)   AS highCount,
                   SUM(CASE WHEN a.status = 'PENDING' THEN 1 ELSE 0 END)    AS pendingCount,
                   MAX(CASE a.risk_level WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END) AS riskWeight,
                   MAX(a.create_time) AS lastTime
            FROM risk_alert a
            LEFT JOIN `user` u ON u.id = a.user_id
            GROUP BY a.user_id, u.real_name, u.student_no
            ORDER BY highCount DESC, alertCount DESC
            LIMIT #{limit}
            """)
    List<Map<String, Object>> selectTopStudents(@Param("limit") int limit);

    /** 处置效率：平均处理时长（分钟） */
    @Select("""
            SELECT COUNT(*)                                            AS handledCount,
                   AVG(TIMESTAMPDIFF(MINUTE, create_time, handle_time)) AS avgMinutes
            FROM risk_alert
            WHERE status = 'HANDLED' AND handle_time IS NOT NULL
            """)
    Map<String, Object> selectHandleEfficiency();

    /** 最早一条待处理工单的时间 —— 用来算「当前积压了多久」 */
    @Select("SELECT MIN(create_time) FROM risk_alert WHERE status = 'PENDING'")
    LocalDateTime selectOldestPendingTime();
}
