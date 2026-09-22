package com.campuscare.security;

import com.campuscare.common.TraceIdHolder;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 给每个 HTTP 请求绑定 traceId。
 *
 * 位置很关键：这是**最外层**的过滤器（{@link Ordered#HIGHEST_PRECEDENCE}），要排在鉴权之前 ——
 * 否则"鉴权失败"这类日志反而没有 traceId，而那恰恰是最需要排查的场景。
 *
 * ⚠️ 异步请求（SSE）不在此处的覆盖范围内：MDC 底层是 ThreadLocal，不会跨线程传递。
 * 这里只负责把 id 绑到请求线程上；SseEmitter 的异步线程需要在任务开始时自己重新绑定
 * （见 ChatService.consultStream / runStream）。
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class TraceIdFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        // 上游（网关、前端、反向代理）带了就复用，这样跨服务/跨系统才是同一条链路
        String traceId = request.getHeader(TraceIdHolder.HEADER);
        if (traceId == null || traceId.isBlank()) {
            traceId = TraceIdHolder.generate();
        }

        TraceIdHolder.set(traceId);
        // 回写响应头：前端排障时可以直接从浏览器 Network 面板拿到 id 去查后端日志
        response.setHeader(TraceIdHolder.HEADER, traceId);

        try {
            filterChain.doFilter(request, response);
        } finally {
            TraceIdHolder.clear();
        }
    }
}
