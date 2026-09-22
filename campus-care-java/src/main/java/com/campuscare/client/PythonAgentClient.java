package com.campuscare.client;

import com.campuscare.common.BizException;
import com.campuscare.common.TraceIdHolder;
import com.campuscare.dto.AgentChatRequest;
import com.campuscare.dto.AgentChatResponse;
import com.campuscare.dto.KnowledgeItem;
import com.campuscare.dto.KnowledgePage;
import com.campuscare.dto.PyEnvelope;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.StreamUtils;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * 调用 Python AI 服务（FastAPI + LangGraph）的客户端，是 Java 与 AI 的边界。
 * chat() 一次性返回，streamChat() 走 SSE 边收边转发。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PythonAgentClient {

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    @Value("${python.ai.base-url}")
    private String baseUrl;

    /**
     * 构造 JSON 请求头，顺带带上链路追踪 id。
     *
     * traceId 在请求体里已经传了一份，这里再走一次请求头是有意为之：
     * 请求头是跨服务的标准通道（Python 侧中间件优先读它），
     * 而体里那一份保证即使中间有代理剥掉了自定义头，链路信息也不会丢。
     */
    private HttpHeaders jsonHeaders() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        applyTraceId(headers);
        return headers;
    }

    /** 把当前线程的 traceId 写进请求头；没有绑定就不带 */
    private void applyTraceId(HttpHeaders headers) {
        String traceId = TraceIdHolder.current();
        if (traceId != null && !traceId.isBlank()) {
            headers.set(TraceIdHolder.HEADER, traceId);
        }
    }

    /**
     * 发起一轮多 Agent 咨询。
     *
     * @param request 用户 id、会话 id、本次消息、历史上下文
     * @return AI 侧的意图 / 回复 / 风险等级 / 检索来源
     */
    public AgentChatResponse chat(AgentChatRequest request) {
        String url = baseUrl + "/api/agent/chat";
        HttpEntity<AgentChatRequest> entity = new HttpEntity<>(request, jsonHeaders());

        long start = System.currentTimeMillis();
        try {
            ResponseEntity<PyEnvelope<AgentChatResponse>> response = restTemplate.exchange(
                    url,
                    HttpMethod.POST,
                    entity,
                    new ParameterizedTypeReference<>() {
                    });

            PyEnvelope<AgentChatResponse> body = response.getBody();
            log.info("调用 Python AI 服务完成，耗时 {} ms，code={}",
                    System.currentTimeMillis() - start, body == null ? null : body.getCode());

            if (body == null || !body.isSuccess() || body.getData() == null) {
                throw new BizException("AI 服务返回异常：" + (body == null ? "响应为空" : body.getMessage()));
            }
            return body.getData();

        } catch (RestClientException e) {
            log.error("调用 Python AI 服务失败: {}", e.getMessage());
            throw new BizException("AI 服务不可用，请确认 campus-care-python 已在 " + baseUrl + " 启动");
        }
    }

    /**
     * SSE 事件回调。event 为事件名（stage / delta / done / error），data 为原始 JSON。
     * 不声明受检异常：ResponseExtractor 只允许抛 IOException，需要上抛的实现方自行包装。
     */
    @FunctionalInterface
    public interface SseEventHandler {
        void onEvent(String event, String data);
    }

    /**
     * 流式调用 /api/agent/chat/stream，把每个 SSE 事件交给 handler。
     * 用 execute 而不是 exchange：后者要读完整个响应体才返回，流式就没意义了。
     */
    public void streamChat(AgentChatRequest request, SseEventHandler handler) {
        String url = baseUrl + "/api/agent/chat/stream";

        restTemplate.execute(url, HttpMethod.POST, req -> {
            applyTraceId(req.getHeaders());
            req.getHeaders().setContentType(MediaType.APPLICATION_JSON);
            req.getHeaders().setAccept(List.of(MediaType.TEXT_EVENT_STREAM));
            StreamUtils.copy(objectMapper.writeValueAsBytes(request), req.getBody());
        }, resp -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(resp.getBody(), StandardCharsets.UTF_8))) {

                String line;
                String eventName = null;
                StringBuilder data = new StringBuilder();

                while ((line = reader.readLine()) != null) {
                    if (line.isEmpty()) {
                        // 空行 = 一个 SSE 帧结束（SSE 协议约定）
                        if (eventName != null && data.length() > 0) {
                            handler.onEvent(eventName, data.toString());
                        }
                        eventName = null;
                        data.setLength(0);
                    } else if (line.startsWith("event:")) {
                        eventName = line.substring("event:".length()).trim();
                    } else if (line.startsWith("data:")) {
                        // 同一个事件可能拆成多行 data:，按协议要拼接
                        data.append(line.substring("data:".length()).trim());
                    }
                    // id: / retry: 等字段本协议用不到，忽略
                }
            }
            return null;
        });
    }

    /**
     * 会话结束时让 AI 生成咨询报告。
     */
    public java.util.Map<String, Object> report(AgentChatRequest request) {
        String url = baseUrl + "/api/agent/report";
        HttpEntity<AgentChatRequest> entity = new HttpEntity<>(request, jsonHeaders());

        try {
            ResponseEntity<PyEnvelope<java.util.Map<String, Object>>> response = restTemplate.exchange(
                    url,
                    HttpMethod.POST,
                    entity,
                    new ParameterizedTypeReference<>() {
                    });
            PyEnvelope<java.util.Map<String, Object>> body = response.getBody();
            if (body == null || !body.isSuccess() || body.getData() == null) {
                throw new BizException("生成报告失败：" + (body == null ? "响应为空" : body.getMessage()));
            }
            return body.getData();
        } catch (RestClientException e) {
            log.error("调用 Python 报告接口失败: {}", e.getMessage());
            throw new BizException("AI 服务不可用，无法生成报告");
        }
    }

    /**
     * 拉取知识库全部条目（心理科普用）。
     *
     * 刻意不带任何查询参数：过滤由 KnowledgeService 在本地做，
     * 百来条纯文本一次取回即可，没必要按关键词反复往返。
     */
    public List<KnowledgeItem> kbItems() {
        String url = baseUrl + "/api/agent/kb/list";
        try {
            ResponseEntity<PyEnvelope<KnowledgePage>> response = restTemplate.exchange(
                    url,
                    HttpMethod.GET,
                    new HttpEntity<>(jsonHeaders()),
                    new ParameterizedTypeReference<>() {
                    });

            PyEnvelope<KnowledgePage> body = response.getBody();
            if (body == null || !body.isSuccess() || body.getData() == null) {
                throw new BizException("知识库返回异常：" + (body == null ? "响应为空" : body.getMessage()));
            }
            List<KnowledgeItem> items = body.getData().getItems();
            return items == null ? List.of() : items;

        } catch (RestClientException e) {
            log.error("拉取知识库失败: {}", e.getMessage());
            throw new BizException("AI 服务不可用，无法加载科普内容");
        }
    }

    /** 健康检查：Python 服务是否在线 */
    public boolean ping() {
        try {
            String result = restTemplate.getForObject(baseUrl + "/api/health", String.class);
            return result != null;
        } catch (Exception e) {
            return false;
        }
    }
}
