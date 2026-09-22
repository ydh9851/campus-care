package com.campuscare.service;

import com.campuscare.client.PythonAgentClient;
import com.campuscare.common.BizException;
import com.campuscare.common.TraceIdHolder;
import com.campuscare.dto.AgentChatRequest;
import com.campuscare.dto.AgentChatResponse;
import com.campuscare.dto.ChatRequest;
import com.campuscare.dto.ChatResponse;
import com.campuscare.entity.Conversation;
import com.campuscare.mapper.ConversationMapper;
import com.campuscare.mapper.MessageMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 咨询编排测试。
 *
 * 这是 Java 与 AI 的边界，也是全项目最容易「静默出错」的一段：
 * AI 返回的字段漏透传一个，前端就少一个提示 —— 不报错、不影响主流程，
 * 但「高危会话到底要不要给人工入口」这种合规判断会直接失效。
 *
 * 所以这里重点守三件事：
 * 1. Python 给的合规字段一个不少地透传到前端
 * 2. traceId 从请求体一路到响应体，两端日志能对上（包括 SSE 的异步线程）
 * 3. AI 失败/越权时，数据库里不留残渣
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("ChatService 咨询编排")
class ChatServiceTest {

    private static final Long USER_ID = 7L;
    private static final Long CONVERSATION_ID = 100L;
    private static final Long ALERT_ID = 999L;
    private static final String CONTENT = "最近总是失眠，压力很大";

    @Mock
    private ConversationMapper conversationMapper;
    @Mock
    private MessageMapper messageMapper;
    @Mock
    private ChatPersistService chatPersistService;
    @Mock
    private PythonAgentClient pythonAgentClient;
    @Mock
    private ObjectMapper objectMapper;

    @InjectMocks
    private ChatService chatService;

    @AfterEach
    void tearDown() {
        // MDC 是线程私有的，但测试线程会被复用 —— 不清会串味到下一个用例
        TraceIdHolder.clear();
    }

    // ---------------------------------------------------------------- 测试夹具

    private Conversation existingConversation() {
        Conversation conversation = new Conversation();
        conversation.setId(CONVERSATION_ID);
        conversation.setUserId(USER_ID);
        conversation.setRiskLevel("LOW");
        conversation.setTurnCount(1);
        return conversation;
    }

    private ChatRequest chatRequest(String content) {
        ChatRequest request = new ChatRequest();
        request.setConversationId(CONVERSATION_ID);
        request.setContent(content);
        return request;
    }

    private AgentChatResponse aiResponse(String reply, String riskLevel) {
        AgentChatResponse response = new AgentChatResponse();
        response.setReply(reply);
        response.setIntent("PSYCH_EMOTION");
        response.setRiskLevel(riskLevel);
        response.setKeywords(List.of("失眠"));
        response.setAiSuggestion("建议预约心理中心面询");
        response.setRagSources(List.of("失眠怎么办"));
        response.setTokens(321);
        response.setRetrievalMode("hybrid");
        response.setPromptVersion(Map.of("reply_base", "a1b2c3d4"));
        response.setDisclaimer("本回复不构成医学诊断");
        response.setNeedHandoff("HIGH".equals(riskLevel));
        return response;
    }

    /** 续聊场景的公共桩。用 lenient：失败路径的用例不需要全部桩生效。 */
    private void givenExistingSession() {
        lenient().when(conversationMapper.selectById(CONVERSATION_ID))
                .thenReturn(existingConversation());
        lenient().when(messageMapper.selectList(any())).thenReturn(List.of());
        lenient().when(chatPersistService.saveTurn(
                anyLong(), any(), anyString(), anyString(), anyString(),
                any(), any(), any(), any())).thenReturn(ALERT_ID);
    }

    // ---------------------------------------------------------------- 字段透传

    @Nested
    @DisplayName("Python 字段透传")
    class Transfer {

        @Test
        @DisplayName("合规与可观测字段一个不少地传给前端")
        void transfersAllFields() {
            givenExistingSession();
            when(pythonAgentClient.chat(any())).thenReturn(aiResponse("我在听", "HIGH"));

            ChatResponse response = chatService.consult(USER_ID, chatRequest(CONTENT));

            assertThat(response.getConversationId()).isEqualTo(CONVERSATION_ID);
            assertThat(response.getReply()).isEqualTo("我在听");
            assertThat(response.getIntent()).isEqualTo("PSYCH_EMOTION");
            assertThat(response.getRiskLevel()).isEqualTo("HIGH");
            assertThat(response.getAlertId()).isEqualTo(ALERT_ID);
            assertThat(response.getRagSources()).containsExactly("失眠怎么办");
            assertThat(response.getTokens()).isEqualTo(321);
            // 下面这几个是「漏了就没人发现」的那种字段
            assertThat(response.getRetrievalMode()).isEqualTo("hybrid");
            assertThat(response.getPromptVersion()).containsEntry("reply_base", "a1b2c3d4");
            assertThat(response.getDisclaimer()).isEqualTo("本回复不构成医学诊断");
            assertThat(response.getNeedHandoff()).isTrue();
        }

        @Test
        @DisplayName("needHandoff 只透传不重算 —— 两端各判一次迟早会打架")
        void doesNotRecomputeNeedHandoff() {
            givenExistingSession();
            AgentChatResponse ai = aiResponse("我在听", "HIGH");
            ai.setNeedHandoff(false); // 故意与风险等级"不一致"，Java 必须原样照搬
            when(pythonAgentClient.chat(any())).thenReturn(ai);

            ChatResponse response = chatService.consult(USER_ID, chatRequest(CONTENT));

            assertThat(response.getNeedHandoff()).isFalse();
        }

        @Test
        @DisplayName("非法风险等级兜底成 LOW，脏数据不进库")
        void fallsBackOnUnknownRiskLevel() {
            givenExistingSession();
            when(pythonAgentClient.chat(any())).thenReturn(aiResponse("我在听", "不认识的等级"));

            ChatResponse response = chatService.consult(USER_ID, chatRequest(CONTENT));

            assertThat(response.getRiskLevel()).isEqualTo("LOW");
        }
    }

    // ---------------------------------------------------------------- traceId

    @Nested
    @DisplayName("traceId 链路")
    class TraceIdChain {

        @Test
        @DisplayName("新建的 traceId 同时进请求体和响应，两端日志能对上")
        void traceIdFlowsToPythonAndBackToFrontend() {
            givenExistingSession();
            when(pythonAgentClient.chat(any())).thenReturn(aiResponse("我在听", "LOW"));

            ChatResponse response = chatService.consult(USER_ID, chatRequest(CONTENT));

            ArgumentCaptor<AgentChatRequest> captor = ArgumentCaptor.forClass(AgentChatRequest.class);
            verify(pythonAgentClient).chat(captor.capture());

            String sentToPython = captor.getValue().getTraceId();
            assertThat(sentToPython).isNotBlank();
            assertThat(response.getTraceId()).isEqualTo(sentToPython);
        }

        @Test
        @DisplayName("过滤器已绑定时复用，不重新生成（否则 Java 日志与前端拿到的对不上）")
        void reusesBoundTraceId() {
            TraceIdHolder.set("fedcba9876543210");
            givenExistingSession();
            when(pythonAgentClient.chat(any())).thenReturn(aiResponse("我在听", "LOW"));

            ChatResponse response = chatService.consult(USER_ID, chatRequest(CONTENT));

            assertThat(response.getTraceId()).isEqualTo("fedcba9876543210");
        }

        @Test
        @DisplayName("SSE 异步线程里重新绑定 traceId —— MDC 不会自动跨线程继承")
        void streamRebindsTraceIdInWorkerThread() throws Exception {
            when(conversationMapper.selectById(CONVERSATION_ID)).thenReturn(existingConversation());
            when(messageMapper.selectList(any())).thenReturn(List.of());

            AtomicReference<String> seenByWorker = new AtomicReference<>();
            AtomicBoolean workerRan = new AtomicBoolean(false);
            doAnswer(invocation -> {
                seenByWorker.set(TraceIdHolder.current());
                workerRan.set(true);
                return null;
            }).when(pythonAgentClient).streamChat(any(), any());

            TraceIdHolder.set("0011223344556677");
            ExecutorService executor = Executors.newSingleThreadExecutor();
            try {
                chatService.consultStream(USER_ID, chatRequest(CONTENT), executor);
                executor.shutdown();
                assertThat(executor.awaitTermination(5, TimeUnit.SECONDS)).isTrue();
            } finally {
                executor.shutdownNow();
            }

            assertThat(workerRan).isTrue();
            assertThat(seenByWorker.get()).isEqualTo("0011223344556677");
        }
    }

    // ---------------------------------------------------------------- 失败与越权

    @Nested
    @DisplayName("失败与越权")
    class Failure {

        @Test
        @DisplayName("续聊时 AI 失败：不删已有会话，历史消息还要保留")
        void keepsExistingConversationOnFailure() {
            givenExistingSession();
            when(pythonAgentClient.chat(any())).thenThrow(new BizException("AI 服务不可用"));

            assertThatThrownBy(() -> chatService.consult(USER_ID, chatRequest(CONTENT)))
                    .isInstanceOf(BizException.class);

            verify(conversationMapper, never()).deleteById(anyLong());
        }

        @Test
        @DisplayName("首次咨询 AI 失败：把刚建的空会话回滚掉，不留垃圾数据")
        void rollsBackNewConversationOnFailure() {
            ChatRequest firstTime = new ChatRequest();
            firstTime.setContent(CONTENT);
            when(conversationMapper.insert(any(Conversation.class))).thenAnswer(invocation -> {
                Conversation saved = invocation.getArgument(0);
                saved.setId(CONVERSATION_ID);
                return 1;
            });
            when(messageMapper.selectList(any())).thenReturn(List.of());
            when(pythonAgentClient.chat(any())).thenThrow(new BizException("AI 服务不可用"));

            assertThatThrownBy(() -> chatService.consult(USER_ID, firstTime))
                    .isInstanceOf(BizException.class);

            verify(conversationMapper).deleteById(CONVERSATION_ID);
        }

        @Test
        @DisplayName("越权：别人的会话不能续聊，也不该白烧一次 AI 调用")
        void rejectsOtherUsersConversation() {
            Conversation others = existingConversation();
            others.setUserId(999L);
            when(conversationMapper.selectById(CONVERSATION_ID)).thenReturn(others);

            assertThatThrownBy(() -> chatService.consult(USER_ID, chatRequest(CONTENT)))
                    .isInstanceOf(BizException.class)
                    .hasMessageContaining("无权");

            verify(pythonAgentClient, never()).chat(any());
        }

        @Test
        @DisplayName("会话不存在时直接报错，不往下走")
        void rejectsMissingConversation() {
            when(conversationMapper.selectById(CONVERSATION_ID)).thenReturn(null);

            assertThatThrownBy(() -> chatService.consult(USER_ID, chatRequest(CONTENT)))
                    .isInstanceOf(BizException.class)
                    .hasMessageContaining("会话不存在");

            verify(pythonAgentClient, never()).chat(any());
        }
    }
}
