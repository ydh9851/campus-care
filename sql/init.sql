-- ============================================================
-- CampusCare 校园心理多 Agent 智能咨询平台 - 数据库初始化脚本
-- MySQL 8.0 / utf8mb4
-- 共 5 张表：user / conversation / message / risk_alert / consult_report
-- ============================================================

DROP DATABASE IF EXISTS campus_care;
CREATE DATABASE campus_care DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE campus_care;

-- ------------------------------------------------------------
-- 1. 用户表
-- ------------------------------------------------------------
CREATE TABLE `user` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `username`    VARCHAR(50)  NOT NULL COMMENT '登录账号',
    `password`    VARCHAR(100) NOT NULL COMMENT 'BCrypt 加密后的密码',
    `real_name`   VARCHAR(50)           DEFAULT NULL COMMENT '真实姓名',
    `student_no`  VARCHAR(30)           DEFAULT NULL COMMENT '学号',
    `phone`       VARCHAR(20)           DEFAULT NULL COMMENT '手机号',
    `email`       VARCHAR(80)           DEFAULT NULL COMMENT '邮箱',
    `role`        VARCHAR(20)  NOT NULL DEFAULT 'STUDENT' COMMENT '角色：STUDENT/COUNSELOR/ADMIN',
    `status`      TINYINT      NOT NULL DEFAULT 1 COMMENT '状态：1启用 0禁用',
    `create_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    KEY `idx_student_no` (`student_no`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '用户表';

-- ------------------------------------------------------------
-- 2. 会话表
-- ------------------------------------------------------------
CREATE TABLE `conversation` (
    `id`            BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
    `user_id`       BIGINT      NOT NULL COMMENT '所属学生',
    `title`         VARCHAR(100)         DEFAULT '新的咨询' COMMENT '会话标题（取首条消息前 20 字）',
    `risk_level`    VARCHAR(10) NOT NULL DEFAULT 'LOW' COMMENT '会话最高风险等级：LOW/MEDIUM/HIGH',
    `turn_count`    INT         NOT NULL DEFAULT 0 COMMENT '对话轮次（1 轮 = 学生 1 条 + AI 1 条）',
    `status`        TINYINT     NOT NULL DEFAULT 1 COMMENT '1进行中 0已结束',
    `create_time`   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `update_time`   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_risk_level` (`risk_level`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '咨询会话表';

-- ------------------------------------------------------------
-- 3. 消息表
-- ------------------------------------------------------------
CREATE TABLE `message` (
    `id`              BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
    `conversation_id` BIGINT      NOT NULL COMMENT '所属会话',
    `user_id`         BIGINT      NOT NULL COMMENT '所属学生',
    `role`            VARCHAR(20) NOT NULL COMMENT '角色：user/assistant',
    `content`         TEXT        NOT NULL COMMENT '消息内容',
    `intent`          VARCHAR(30)          DEFAULT NULL COMMENT '意图：PSYCH_EMOTION/KNOWLEDGE_QUERY/RISK_ALERT/CHITCHAT',
    `risk_level`      VARCHAR(10)          DEFAULT NULL COMMENT '本条消息风险等级',
    `tokens`          INT         NOT NULL DEFAULT 0 COMMENT '消耗 token（统计用）',
    `create_time`     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_conversation_id` (`conversation_id`),
    KEY `idx_user_id` (`user_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '消息表';

-- ------------------------------------------------------------
-- 4. 风险预警工单表（统一工单池）
--
-- 设计说明：这里刻意把「对话预警」和「量表测评预警」放在同一张表里，
-- 用 source 区分来源。原因是辅导员的诉求是「一屏看到所有需要关注的学生」，
-- 如果两个来源各建一张表，辅导员就得在两个页面之间来回切换，很容易漏掉高危件。
-- 代价是 conversation_id / message_id 对量表来源必须允许为空。
-- ------------------------------------------------------------
CREATE TABLE `risk_alert` (
    `id`                   BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
    `source`               VARCHAR(20) NOT NULL DEFAULT 'CHAT' COMMENT '来源：CHAT 对话预警 / ASSESSMENT 量表测评预警',
    `conversation_id`      BIGINT               DEFAULT NULL COMMENT '关联会话（量表来源为 NULL）',
    `message_id`           BIGINT               DEFAULT NULL COMMENT '触发预警的消息（量表来源为 NULL）',
    `assessment_record_id` BIGINT               DEFAULT NULL COMMENT '关联测评记录（对话来源为 NULL）',
    `user_id`              BIGINT      NOT NULL COMMENT '涉及学生',
    `risk_level`           VARCHAR(10) NOT NULL COMMENT '风险等级：MEDIUM/HIGH',
    `keywords`             VARCHAR(255)         DEFAULT NULL COMMENT '命中的关键词或高危题号，逗号分隔',
    `content`              TEXT        NOT NULL COMMENT '触发预警的原文（对话原话 / 量表结论）',
    `ai_suggestion`        VARCHAR(1000)        DEFAULT NULL COMMENT 'AI 或规则生成的处置建议',
    `status`               VARCHAR(20) NOT NULL DEFAULT 'PENDING' COMMENT '处理状态：PENDING/HANDLED/CLOSED',
    `handler_id`           BIGINT               DEFAULT NULL COMMENT '处理人（辅导员）',
    `handle_remark`        VARCHAR(500)         DEFAULT NULL COMMENT '处理备注',
    `create_time`          DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `handle_time`          DATETIME             DEFAULT NULL COMMENT '处理时间',
    PRIMARY KEY (`id`),
    KEY `idx_status` (`status`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_risk_level` (`risk_level`),
    KEY `idx_source` (`source`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '风险预警工单表（统一工单池）';

-- ------------------------------------------------------------
-- 5. 咨询报告表
-- ------------------------------------------------------------
CREATE TABLE `consult_report` (
    `id`              BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
    `conversation_id` BIGINT      NOT NULL COMMENT '关联会话',
    `user_id`         BIGINT      NOT NULL COMMENT '所属学生',
    `summary`         VARCHAR(1000)        DEFAULT NULL COMMENT '对话摘要',
    `emotion_score`   INT         NOT NULL DEFAULT 60 COMMENT '情绪评分 0-100，越高越积极',
    `risk_level`      VARCHAR(10) NOT NULL DEFAULT 'LOW' COMMENT '综合风险等级',
    `suggestion`      VARCHAR(1000)        DEFAULT NULL COMMENT '干预建议',
    `create_time`     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_conversation_id` (`conversation_id`),
    KEY `idx_user_id` (`user_id`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '咨询报告表';

-- ------------------------------------------------------------
-- 6. 心理测评记录表
--
-- 为什么答题明细存成一串逗号分隔的分值，而不是每题一行？
-- 因为量表本身是不可变的（题目和计分规则固定），明细只用于「回看当时怎么答的」，
-- 不需要按单题做查询或聚合。存成一行能避免 PHQ-9 一次测评就写 9 行数据。
-- 如果以后要做「某道题的群体统计」，再拆表也不迟 —— 那是另一个量级的需求。
-- ------------------------------------------------------------
CREATE TABLE `assessment_record` (
    `id`              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `user_id`         BIGINT       NOT NULL COMMENT '学生 id',
    `scale_code`      VARCHAR(20)  NOT NULL COMMENT '量表编码：PHQ9 / GAD7',
    `scale_name`      VARCHAR(60)  NOT NULL COMMENT '量表名称（冗余存一份，方便列表直接展示）',
    `total_score`     INT          NOT NULL COMMENT '总分',
    `severity`        VARCHAR(30)  NOT NULL COMMENT '严重程度编码：NONE/MILD/MODERATE/MODERATELY_SEVERE/SEVERE',
    `severity_label`  VARCHAR(40)  NOT NULL COMMENT '严重程度中文，如「中度抑郁」',
    `risk_level`      VARCHAR(10)  NOT NULL DEFAULT 'LOW' COMMENT '换算出的风险等级：LOW/MEDIUM/HIGH',
    `answers`         VARCHAR(500) NOT NULL COMMENT '答题明细，逗号分隔的选项分值，如 1,2,0,3,...',
    `high_risk_items` VARCHAR(100)          DEFAULT NULL COMMENT '触发高危的题号，如「9」',
    `create_time`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_scale_code` (`scale_code`),
    KEY `idx_create_time` (`create_time`)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '心理测评记录表';

-- ------------------------------------------------------------
-- 初始化数据
-- 密码明文均为 123456，下面存的是 BCrypt 值
-- ------------------------------------------------------------
INSERT INTO `user` (`username`, `password`, `real_name`, `student_no`, `role`)
VALUES ('student01', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iKTVKIUi', '测试学生', '2022001', 'STUDENT'),
       ('teacher01', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iKTVKIUi', '测试辅导员', NULL, 'COUNSELOR');

SELECT 'CampusCare 初始化完成' AS msg;
