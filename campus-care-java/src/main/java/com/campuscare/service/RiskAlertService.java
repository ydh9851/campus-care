package com.campuscare.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.campuscare.common.BizException;
import com.campuscare.common.RiskLevel;
import com.campuscare.entity.RiskAlert;
import com.campuscare.mapper.RiskAlertMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 风险工单服务：建单 + 辅导员工作台的查询与处置。
 *
 * 建单入口只有 createAlert 一个，对话预警和量表预警都走它，
 * 保证建单门槛、keywords 拼接、初始状态这些规则只有一份实现。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RiskAlertService {

    /** 工单来源：对话预警 */
    public static final String SOURCE_CHAT = "CHAT";
    /** 工单来源：量表测评预警 */
    public static final String SOURCE_ASSESSMENT = "ASSESSMENT";

    private final RiskAlertMapper riskAlertMapper;

    /** 建单参数 */
    public record AlertDraft(
            Long userId,
            String source,
            Long conversationId,
            Long messageId,
            Long assessmentRecordId,
            RiskLevel riskLevel,
            List<String> keywords,
            String content,
            String suggestion) {
    }

    /**
     * 创建一张风险工单，等级未达门槛时返回 null。
     *
     * 本方法自身不加 @Transactional：它在 saveTurn() 的事务里被调用，
     * 以 REQUIRED 传播加入外层事务，这样「AI 回复 + 工单 + 会话轮次」才能同生共死。
     */
    public Long createAlert(AlertDraft draft) {
        if (draft.riskLevel() == null || !draft.riskLevel().needAlert()) {
            return null;
        }

        RiskAlert alert = new RiskAlert();
        alert.setSource(draft.source());
        alert.setUserId(draft.userId());
        alert.setConversationId(draft.conversationId());
        alert.setMessageId(draft.messageId());
        alert.setAssessmentRecordId(draft.assessmentRecordId());
        alert.setRiskLevel(draft.riskLevel().name());
        alert.setKeywords(draft.keywords() == null ? null : String.join(",", draft.keywords()));
        alert.setContent(draft.content());
        alert.setAiSuggestion(draft.suggestion());
        alert.setStatus("PENDING");
        riskAlertMapper.insert(alert);

        log.warn("生成风险工单: id={}, source={}, userId={}, level={}, keywords={}",
                alert.getId(), draft.source(), draft.userId(), draft.riskLevel(), alert.getKeywords());
        return alert.getId();
    }

    /**
     * 分页查询工单列表。
     *
     * @param status    处理状态，null 表示全部
     * @param riskLevel 风险等级，null 表示全部
     */
    public IPage<RiskAlert> page(long current, long size, String status, String riskLevel) {
        Page<RiskAlert> page = new Page<>(current, Math.min(size, 100));

        QueryWrapper<RiskAlert> wrapper = Wrappers.query();
        wrapper.eq(status != null && !status.isBlank(), "status", status);
        wrapper.eq(riskLevel != null && !riskLevel.isBlank(), "risk_level", riskLevel);

        // risk_level 是字符串，按字典序排会得到 MEDIUM > LOW > HIGH，高危反而沉到最后，
        // 所以用 CASE 显式定义权重。last() 拼接的是代码里的常量，不涉及外部入参，无注入风险。
        wrapper.last("ORDER BY CASE risk_level WHEN 'HIGH' THEN 1 "
                + "WHEN 'MEDIUM' THEN 2 ELSE 3 END ASC, create_time DESC");

        return riskAlertMapper.selectPage(page, wrapper);
    }

    /** 处理工单：填处置备注后状态改为 HANDLED，只允许处理 PENDING 的 */
    @Transactional(rollbackFor = Exception.class)
    public void handle(Long alertId, Long handlerId, String remark) {
        RiskAlert alert = riskAlertMapper.selectById(alertId);
        if (alert == null) {
            throw new BizException("预警记录不存在");
        }
        if (!"PENDING".equals(alert.getStatus())) {
            throw new BizException("该预警已被处理，无需重复操作");
        }

        alert.setStatus("HANDLED");
        alert.setHandlerId(handlerId);
        alert.setHandleRemark(remark);
        alert.setHandleTime(LocalDateTime.now());
        riskAlertMapper.updateById(alert);

        log.info("预警已处理: alertId={}, handlerId={}, remark={}", alertId, handlerId, remark);
    }

    /** 风险统计 */
    public Map<String, Object> statistics() {
        return riskAlertMapper.selectStatistics();
    }

    /** 某学生待处理工单数 */
    public long countPending(Long userId) {
        return riskAlertMapper.countPendingByUser(userId);
    }
}
