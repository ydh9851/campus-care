package com.campuscare.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.campuscare.client.PythonAgentClient;
import com.campuscare.common.BizException;
import com.campuscare.common.RiskLevel;
import com.campuscare.dto.AgentChatRequest;
import com.campuscare.dto.AgentChatResponse;
import com.campuscare.dto.ChatRequest;
import com.campuscare.dto.ChatResponse;
import com.campuscare.dto.HistoryMessage;
import com.campuscare.entity.Conversation;
import com.campuscare.entity.Message;
import com.campuscare.mapper.ConversationMapper;
import com.campuscare.mapper.MessageMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.atomic.AtomicReference;

/**
 * 咨询编排：取/建会话 → 取历史上下文 → 调 Python 多 Agent → 短事务落库 → 返回。
 *
 * 调 AI 排在写库之前，AI 失败时不会留下残缺数据。
 * 对外两个入口，写入顺序一致：consult() 一次性返回，consultStream() 走 SSE 流式。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatService {

    private final ConversationMapper conversationMapper;
    private final MessageMapper messageMapper;
    private final ChatPersistService chatPersistService;
    private final PythonAgentClient pythonAgentClient;
    private final ObjectMapper objectMapper;

    /** 传给 AI 的历史条数（太多会浪费 token，太少会丢上下文） */
    private static final int HISTORY_LIMIT = 10;

    /** 会话标题长度 */
    private static final int TITLE_LENGTH = 20;

    /** SSE 连接最长保持时间：LLM 慢，给足 3 分钟 */
    private static final long SSE_TIMEOUT_MS = 180_000L;

    // ---------- 非流式入口 ----------

    /**
     * 发起一轮咨询（一次性返回）。
     * 刻意不加 @Transactional：中间要调 LLM，长事务会占死数据库连接，
     * 写操作收敛在 ChatPersistService 的短事务里。
     */
    public ChatResponse consult(Long userId, ChatRequest request) {

        // ---------- 1. 取会话，没有就新建 ----------
        SessionRef ref = resolveSession(userId, request);
        Conversation conversation = ref.conversation();

        // ---------- 2. 调用 Python 多 Agent 服务（失败时数据库保持干净） ----------
        AgentChatResponse agentResponse;
        try {
            agentResponse = pythonAgentClient.chat(
                    buildAgentRequest(userId, conversation, request.getContent()));
        } catch (RuntimeException e) {
            rollbackIfCreated(ref);
            throw e;
        }
        RiskLevel riskLevel = RiskLevel.of(agentResponse.getRiskLevel());

        // ---------- 3. 一次短事务落库：学生消息 + AI 回复 + 预警 + 会话轮次/风险等级 ----------
        Long alertId = chatPersistService.saveTurn(
                userId,
                conversation,
                request.getContent(),
                agentResponse.getReply(),
                agentResponse.getIntent(),
                riskLevel,
                agentResponse.getKeywords(),
                agentResponse.getAiSuggestion(),
                agentResponse.getTokens());

        // ---------- 4. 组装返回 ----------
        ChatResponse response = new ChatResponse();
        response.setConversationId(conversation.getId());
        response.setReply(agentResponse.getReply());
        response.setIntent(agentResponse.getIntent());
        response.setRiskLevel(riskLevel.name());
        response.setAlertId(alertId);
        response.setRagSources(agentResponse.getRagSources());
        response.setTokens(agentResponse.getTokens());
        return response;
    }

    // ---------- 流式入口（SSE） ----------

    /**
     * 发起一轮流式咨询。
     * SseEmitter 必须在请求线程里创建，实际处理丢给线程池，避免占死 Tomcat 工作线程。
     */
    public SseEmitter consultStream(Long userId, ChatRequest request, ExecutorService executor) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        executor.submit(() -> runStream(userId, request, emitter));
        return emitter;
    }

    /**
     * 流式链路主体。与一次性接口的区别是落库时机：
     * 必须等到 done 事件（流结束）才落库，流式过程中拿到的只是半截回复。
     */
    private void runStream(Long userId, ChatRequest request, SseEmitter emitter) {
        SessionRef ref = null;
        try {
            // ---------- 1. 取会话 ----------
            ref = resolveSession(userId, request);
            Conversation conversation = ref.conversation();

            // 先下发会话 id
            Map<String, Object> open = new HashMap<>();
            open.put("conversationId", conversation.getId());
            emitter.send(SseEmitter.event().name("open")
                    .data(objectMapper.writeValueAsString(open)));

            // ---------- 2. 调 Python 流式接口，逐事件透传 ----------
            // done 事件先攒着：既要发给前端，又要用来落库（补上 alertId 后再发）
            AtomicReference<String> doneJson = new AtomicReference<>();
            AgentChatRequest agentRequest = buildAgentRequest(userId, conversation, request.getContent());

            pythonAgentClient.streamChat(agentRequest, (event, data) -> {
                if ("done".equals(event)) {
                    doneJson.set(data);
                    return;
                }
                try {
                    emitter.send(SseEmitter.event().name(event).data(data));
                } catch (IOException e) {
                    // 客户端断开（关页面/切走）时抛非受检异常，交由外层收尾并停止读取 Python 流
                    throw new UncheckedIOException(e);
                }
            });

            if (doneJson.get() == null) {
                throw new BizException("AI 服务未返回结果");
            }

            // ---------- 3. 落库（此时 AI 已全部生成完，数据是完整的） ----------
            Map<String, Object> done = objectMapper.readValue(
                    doneJson.get(), new TypeReference<Map<String, Object>>() {
                    });
            AgentChatResponse res = objectMapper.convertValue(done, AgentChatResponse.class);
            RiskLevel riskLevel = RiskLevel.of(res.getRiskLevel());

            Long alertId = chatPersistService.saveTurn(
                    userId,
                    conversation,
                    request.getContent(),
                    res.getReply(),
                    res.getIntent(),
                    riskLevel,
                    res.getKeywords(),
                    res.getAiSuggestion(),
                    res.getTokens());

            // ---------- 4. 补上落库结果再发 done ----------
            done.put("conversationId", conversation.getId());
            done.put("alertId", alertId);
            emitter.send(SseEmitter.event().name("done")
                    .data(objectMapper.writeValueAsString(done)));
            emitter.complete();

        } catch (Exception e) {
            log.error("流式咨询失败: {}", e.getMessage());
            // 和一次性接口一样：AI 没成功，首次咨询新建的空会话要回滚掉
            if (ref != null) {
                rollbackIfCreated(ref);
            }
            try {
                Map<String, Object> error = new HashMap<>();
                error.put("message", e.getMessage() == null ? "服务异常" : e.getMessage());
                emitter.send(SseEmitter.event().name("error")
                        .data(objectMapper.writeValueAsString(error)));
            } catch (Exception ignore) {
                // 客户端已经断开，推不出去就算了
                log.debug("推送 error 事件失败: {}", ignore.getMessage());
            }
            emitter.completeWithError(e);
        }
    }

    // ---------- 共用逻辑 ----------

    /** 会话解析结果。createdNow=true 表示这次刚建出来，AI 失败时要回滚 */
    private record SessionRef(Conversation conversation, boolean createdNow) {
    }

    /** 取会话（续聊）或新建会话，并做越权校验。 */
    private SessionRef resolveSession(Long userId, ChatRequest request) {
        if (request.getConversationId() == null) {
            return new SessionRef(createConversation(userId, request.getContent()), true);
        }
        Conversation conversation = conversationMapper.selectById(request.getConversationId());
        if (conversation == null) {
            throw new BizException("会话不存在");
        }
        // 越权校验：只能操作自己的会话
        if (!conversation.getUserId().equals(userId)) {
            throw new BizException(403, "无权访问他人的会话");
        }
        return new SessionRef(conversation, false);
    }

    /** 组装发给 AI 的请求：历史消息 + 本次输入。流式与非流式共用同一套上下文策略 */
    private AgentChatRequest buildAgentRequest(Long userId, Conversation conversation, String content) {
        List<HistoryMessage> history = loadHistory(conversation.getId());
        history.add(new HistoryMessage("user", content));

        AgentChatRequest agentRequest = new AgentChatRequest();
        agentRequest.setUserId(userId);
        agentRequest.setConversationId(conversation.getId());
        agentRequest.setMessage(content);
        agentRequest.setHistory(history);
        return agentRequest;
    }

    /** 首次咨询新建的会话在 AI 失败时回滚掉；续聊场景不能删，历史消息还要保留 */
    private void rollbackIfCreated(SessionRef ref) {
        if (ref != null && ref.createdNow()) {
            conversationMapper.deleteById(ref.conversation().getId());
            log.warn("AI 调用失败，已回滚本次新建的空会话: conversationId={}", ref.conversation().getId());
        }
    }

    /** 新建会话，标题取首条消息前 20 字 */
    private Conversation createConversation(Long userId, String firstContent) {
        Conversation conversation = new Conversation();
        conversation.setUserId(userId);
        conversation.setTitle(truncate(firstContent, TITLE_LENGTH));
        conversation.setRiskLevel(RiskLevel.LOW.name());
        conversation.setTurnCount(0);
        conversation.setStatus(1);
        conversationMapper.insert(conversation);
        log.info("新建会话: id={}, userId={}", conversation.getId(), userId);
        return conversation;
    }

    /** 取最近 N 条消息，按时间正序返回（LLM 需要"先早后晚"） */
    private List<HistoryMessage> loadHistory(Long conversationId) {
        List<Message> messages = messageMapper.selectList(
                Wrappers.<Message>lambdaQuery()
                        .eq(Message::getConversationId, conversationId)
                        .orderByDesc(Message::getId)
                        .last("LIMIT " + HISTORY_LIMIT));

        List<HistoryMessage> history = new ArrayList<>(messages.size());
        for (Message message : messages) {
            history.add(new HistoryMessage(message.getRole(), message.getContent()));
        }
        Collections.reverse(history);
        return history;
    }

    /** 我的会话列表（按最后更新时间倒序） */
    public List<Conversation> listConversations(Long userId) {
        return conversationMapper.selectList(
                Wrappers.<Conversation>lambdaQuery()
                        .eq(Conversation::getUserId, userId)
                        .orderByDesc(Conversation::getUpdateTime));
    }

    /** 某个会话的完整消息记录 */
    public List<Message> listMessages(Long userId, Long conversationId) {
        Conversation conversation = conversationMapper.selectById(conversationId);
        if (conversation == null) {
            throw new BizException("会话不存在");
        }
        if (!conversation.getUserId().equals(userId)) {
            throw new BizException(403, "无权访问他人的会话");
        }
        return messageMapper.selectList(
                Wrappers.<Message>lambdaQuery()
                        .eq(Message::getConversationId, conversationId)
                        .orderByAsc(Message::getId));
    }

    /** 字符串截断，防止标题超长 */
    private String truncate(String text, int maxLength) {
        if (text == null) {
            return "新的咨询";
        }
        return text.length() <= maxLength ? text : text.substring(0, maxLength) + "...";
    }
}
