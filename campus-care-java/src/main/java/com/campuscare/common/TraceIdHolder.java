package com.campuscare.common;

import org.slf4j.MDC;

import java.util.UUID;

/**
 * 链路追踪 id 的持有者。
 *
 * 为什么放进 MDC 而不是到处传参：一次咨询会穿过过滤器、鉴权、会话解析、Service、
 * RestTemplate 客户端，最后还要进 SSE 的异步线程。如果靠每处手写 {@code traceId={}} 占位符，
 * 漏一处链路就断一处，新写的代码也很容易忘。
 * 放进 MDC 后 logback pattern 里写一次 {@code %X{traceId}} 就够了，所有日志自动带上。
 *
 * traceId 的生成口径与 Python 侧保持一致（UUID 去横线取前 16 位），
 * 这样 Java 与 Python 的日志放在一起看时，一眼能认出是同一条链路。
 */
public final class TraceIdHolder {

    /** MDC 的 key，必须与 logback-spring.xml 里的 %X{traceId} 一致 */
    public static final String MDC_KEY = "traceId";

    /** 跨服务传递用的请求头（Java → Python），Python 侧也会回写同名响应头 */
    public static final String HEADER = "X-Trace-Id";

    private TraceIdHolder() {
    }

    /** 当前线程绑定的 traceId；不在请求上下文里时为 null */
    public static String current() {
        return MDC.get(MDC_KEY);
    }

    /** 取当前 traceId，没有就生成一个并绑定。业务代码通常只用这个方法。 */
    public static String currentOrCreate() {
        String traceId = current();
        if (traceId == null || traceId.isBlank()) {
            traceId = generate();
            MDC.put(MDC_KEY, traceId);
        }
        return traceId;
    }

    /** 绑定 traceId（异步线程开始任务时用）；传空表示解绑 */
    public static void set(String traceId) {
        if (traceId == null || traceId.isBlank()) {
            MDC.remove(MDC_KEY);
        } else {
            MDC.put(MDC_KEY, traceId);
        }
    }

    /**
     * 解绑。
     * Tomcat 的线程是复用的，请求结束必须清掉，否则下一个请求会"继承"上一个请求的 traceId，
     * 日志看起来一切正常，实际全是错的 —— 这种问题排查起来极其费劲。
     */
    public static void clear() {
        MDC.remove(MDC_KEY);
    }

    /** 生成 traceId：UUID 去横线后取前 16 位，与 Python 侧口径一致 */
    public static String generate() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 16);
    }
}
