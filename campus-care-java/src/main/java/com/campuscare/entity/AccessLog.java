package com.campuscare.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 敏感数据访问审计日志。
 *
 * 只记录需要追责的动作（查阅他人心理档案、处置风险工单），
 * 不记录普通业务写入 —— 审计表一旦变成"全量操作日志"，
 * 数据量会迅速失控，真正要查的那几条反而被淹没。
 *
 * create_time 不在这里赋值：MyBatis-Plus 默认跳过 null 字段，
 * 由数据库的 CURRENT_TIMESTAMP 填，避免应用服务器与数据库时钟不一致。
 */
@Data
@TableName("access_log")
public class AccessLog implements Serializable {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 操作人（辅导员/管理员） */
    private Long operatorId;

    /** 操作人账号，冗余存储：改名或注销后日志仍可读 */
    private String operatorName;

    /** VIEW_PROFILE / HANDLE_ALERT */
    private String action;

    /** USER / ALERT */
    private String targetType;

    private Long targetId;

    private String detail;

    private String ip;

    private LocalDateTime createTime;
}
