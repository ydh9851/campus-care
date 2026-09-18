package com.campuscare.controller;

import com.campuscare.common.Result;
import com.campuscare.dto.ChatRequest;
import com.campuscare.dto.ChatResponse;
import com.campuscare.entity.Conversation;
import com.campuscare.entity.Message;
import com.campuscare.security.SecurityUtils;
import com.campuscare.service.ChatService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.concurrent.ExecutorService;

/**
 * 咨询接口：核心链路入口。
 */
@Tag(name = "02-咨询", description = "发起咨询、会话列表、消息记录")
@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;
    private final ExecutorService sseExecutor;

    @Operation(summary = "发起咨询",
            description = "conversationId 为空则新建会话。内部会依次走 意图识别 → RAG 检索 → 风险预警 → 生成回复")
    @PostMapping("/consult")
    public Result<ChatResponse> consult(@Valid @RequestBody ChatRequest request) {
        return Result.ok(chatService.consult(SecurityUtils.currentUserId(), request));
    }

    /**
     * SSE 流式咨询。
     *
     * 事件名：
     *   open  {conversationId}                     会话已就绪
     *   stage {node,label,elapsedMs,detail}        某个 Agent 节点跑完（带真实耗时）
     *   delta {text}                               一小段回复正文
     *   done  {reply,intent,riskLevel,...,alertId} 全部结束（此时才落库）
     *   error {message}                            出错，这一轮不落库
     *
     * 不写 produces = TEXT_EVENT_STREAM_VALUE：限定后参数校验失败时无法返回 JSON 错误体。
     * 返回 SseEmitter 时 Spring 会自动把响应类型设为 text/event-stream。
     */
    @Operation(summary = "发起咨询（SSE 流式）",
            description = "逐 token 推送回复，且每个 Agent 节点跑完先推一个带真实耗时的 stage 事件。"
                    + "事件名：open / stage / delta / done / error。流结束后才落库。")
    @PostMapping("/consult/stream")
    public SseEmitter consultStream(@Valid @RequestBody ChatRequest request) {
        return chatService.consultStream(SecurityUtils.currentUserId(), request, sseExecutor);
    }

    @Operation(summary = "我的会话列表")
    @GetMapping("/conversations")
    public Result<List<Conversation>> conversations() {
        return Result.ok(chatService.listConversations(SecurityUtils.currentUserId()));
    }

    @Operation(summary = "某个会话的消息记录")
    @GetMapping("/conversations/{conversationId}/messages")
    public Result<List<Message>> messages(@PathVariable Long conversationId) {
        return Result.ok(chatService.listMessages(SecurityUtils.currentUserId(), conversationId));
    }
}
