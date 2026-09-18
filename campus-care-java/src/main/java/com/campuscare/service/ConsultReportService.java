package com.campuscare.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.campuscare.client.PythonAgentClient;
import com.campuscare.common.BizException;
import com.campuscare.dto.AgentChatRequest;
import com.campuscare.dto.HistoryMessage;
import com.campuscare.entity.ConsultReport;
import com.campuscare.entity.Conversation;
import com.campuscare.entity.Message;
import com.campuscare.mapper.ConsultReportMapper;
import com.campuscare.mapper.ConversationMapper;
import com.campuscare.mapper.MessageMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 咨询报告服务：把整个会话交给 LLM 总结，产出情绪评分 + 风险等级 + 干预建议。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ConsultReportService {

    private final ConsultReportMapper consultReportMapper;
    private final ConversationMapper conversationMapper;
    private final MessageMapper messageMapper;
    private final PythonAgentClient pythonAgentClient;

    /**
     * 生成（或重新生成）某会话的咨询报告。一个会话一份，重复生成会覆盖。
     */
    @Transactional(rollbackFor = Exception.class)
    public ConsultReport generate(Long userId, Long conversationId) {
        Conversation conversation = conversationMapper.selectById(conversationId);
        if (conversation == null) {
            throw new BizException("会话不存在");
        }
        if (!conversation.getUserId().equals(userId)) {
            throw new BizException(403, "无权访问他人的会话");
        }

        // 1. 取全部消息作为总结材料
        List<Message> messages = messageMapper.selectList(
                Wrappers.<Message>lambdaQuery()
                        .eq(Message::getConversationId, conversationId)
                        .orderByAsc(Message::getId));
        if (messages.isEmpty()) {
            throw new BizException("该会话还没有聊天记录，无法生成报告");
        }

        List<HistoryMessage> history = new ArrayList<>(messages.size());
        for (Message message : messages) {
            history.add(new HistoryMessage(message.getRole(), message.getContent()));
        }

        // 2. 交给 Python 侧 LLM 总结
        AgentChatRequest request = new AgentChatRequest();
        request.setUserId(userId);
        request.setConversationId(conversationId);
        request.setMessage("请对这个会话生成咨询报告");
        request.setHistory(history);

        Map<String, Object> data = pythonAgentClient.report(request);

        // 3. 落库（有则覆盖）
        ConsultReport report = consultReportMapper.selectOne(
                Wrappers.<ConsultReport>lambdaQuery().eq(ConsultReport::getConversationId, conversationId));
        boolean isNew = (report == null);
        if (isNew) {
            report = new ConsultReport();
            report.setConversationId(conversationId);
            report.setUserId(userId);
        }
        report.setSummary(str(data.get("summary")));
        report.setEmotionScore(toInt(data.get("emotionScore"), 60));
        report.setRiskLevel(str(data.getOrDefault("riskLevel", conversation.getRiskLevel())));
        report.setSuggestion(str(data.get("suggestion")));

        if (isNew) {
            consultReportMapper.insert(report);
        } else {
            consultReportMapper.updateById(report);
        }

        // 4. 会话标记为已结束
        conversation.setStatus(0);
        conversationMapper.updateById(conversation);

        log.info("生成咨询报告: conversationId={}, emotionScore={}, riskLevel={}",
                conversationId, report.getEmotionScore(), report.getRiskLevel());
        return report;
    }

    /** 查询已有报告 */
    public ConsultReport get(Long userId, Long conversationId) {
        ConsultReport report = consultReportMapper.selectOne(
                Wrappers.<ConsultReport>lambdaQuery().eq(ConsultReport::getConversationId, conversationId));
        if (report == null) {
            throw new BizException("该会话还没有生成报告");
        }
        if (!report.getUserId().equals(userId)) {
            throw new BizException(403, "无权访问他人的报告");
        }
        return report;
    }

    private String str(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private Integer toInt(Object value, int defaultValue) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return value == null ? defaultValue : Integer.parseInt(String.valueOf(value));
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }
}
