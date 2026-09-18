package com.campuscare.service;

import com.campuscare.common.RiskLevel;
import com.campuscare.entity.Conversation;
import com.campuscare.entity.Message;
import com.campuscare.mapper.ConversationMapper;
import com.campuscare.mapper.MessageMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 咨询结果落库。事务边界收敛在这里，ChatService 只负责编排、不开事务。
 *
 * 本方法在 AI 调用成功之后才执行，因此写下的数据一定是完整的；
 * AI 失败时不会走到这里，数据库不会留下半成品。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatPersistService {

    private final ConversationMapper conversationMapper;
    private final MessageMapper messageMapper;
    private final RiskAlertService riskAlertService;

    /**
     * 一轮对话的完整落库：学生消息 + AI 回复 + 风险工单 + 会话轮次/等级。
     * 四步要么都成功，要么都回滚。
     *
     * @return 生成的工单 id，没有则为 null
     */
    @Transactional(rollbackFor = Exception.class)
    public Long saveTurn(Long userId,
                         Conversation conversation,
                         String userContent,
                         String replyText,
                         String intent,
                         RiskLevel riskLevel,
                         List<String> keywords,
                         String aiSuggestion,
                         Integer tokens) {

        // 1. 学生消息。和 AI 回复放在同一个事务里，
        //    否则会出现「只有提问、没有回答」的残缺会话，轮次也和消息行数对不上。
        Message userMessage = new Message();
        userMessage.setConversationId(conversation.getId());
        userMessage.setUserId(userId);
        userMessage.setRole("user");
        userMessage.setContent(userContent);
        messageMapper.insert(userMessage);

        // 2. AI 回复
        Message assistantMessage = new Message();
        assistantMessage.setConversationId(conversation.getId());
        assistantMessage.setUserId(userId);
        assistantMessage.setRole("assistant");
        assistantMessage.setContent(replyText);
        assistantMessage.setIntent(intent);
        assistantMessage.setRiskLevel(riskLevel.name());
        assistantMessage.setTokens(tokens == null ? 0 : tokens);
        messageMapper.insert(assistantMessage);

        // 3. 建风险工单。走 RiskAlertService 统一入口，与量表预警共用同一套建单规则。
        //    注意 message_id 指向学生那句原话，而不是 AI 的回复。
        Long alertId = riskAlertService.createAlert(new RiskAlertService.AlertDraft(
                userId,
                RiskAlertService.SOURCE_CHAT,
                conversation.getId(),
                userMessage.getId(),
                null,
                riskLevel,
                keywords,
                userMessage.getContent(),
                aiSuggestion));

        // 4. 会话轮次 +1，风险等级只升不降
        conversationMapper.increaseTurnCount(conversation.getId(), riskLevel.name());

        return alertId;
    }
}
