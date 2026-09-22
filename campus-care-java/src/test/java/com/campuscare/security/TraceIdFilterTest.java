package com.campuscare.security;

import com.campuscare.common.TraceIdHolder;
import jakarta.servlet.FilterChain;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

/**
 * traceId 过滤器测试。
 *
 * 为什么值得单独测：它有三个「静默出错」的失败模式，
 * 都不会抛异常、不会影响业务、日志看起来也正常 ——
 *
 * 1. 没清 MDC —— Tomcat 线程复用，下一个请求"继承"上一个的 id，查日志时张冠李戴
 * 2. 没复用上游 header —— 跨服务链路断成两截，一半 id 在这儿、一半在那儿
 * 3. 没回写响应头 —— 前端拿不到 id，报障时只能说"刚才那一下"
 */
@DisplayName("TraceIdFilter")
class TraceIdFilterTest {

    private final TraceIdFilter filter = new TraceIdFilter();

    @AfterEach
    void tearDown() {
        TraceIdHolder.clear();
    }

    @Nested
    @DisplayName("id 的来源")
    class Resolution {

        @Test
        @DisplayName("上游没带就自动生成，并回写响应头")
        void generatesWhenAbsent() throws Exception {
            MockHttpServletRequest request = new MockHttpServletRequest();
            MockHttpServletResponse response = new MockHttpServletResponse();
            FilterChain chain = mock(FilterChain.class);

            filter.doFilterInternal(request, response, chain);

            String traceId = response.getHeader(TraceIdHolder.HEADER);
            assertThat(traceId).isNotBlank().hasSize(16);
            verify(chain).doFilter(request, response);
        }

        @Test
        @DisplayName("复用了上游传来的 X-Trace-Id —— 跨服务才是同一条链路")
        void reusesUpstreamTraceId() throws Exception {
            MockHttpServletRequest request = new MockHttpServletRequest();
            request.addHeader(TraceIdHolder.HEADER, "abcdef0123456789");
            MockHttpServletResponse response = new MockHttpServletResponse();

            filter.doFilterInternal(request, response, mock(FilterChain.class));

            assertThat(response.getHeader(TraceIdHolder.HEADER)).isEqualTo("abcdef0123456789");
        }

        @Test
        @DisplayName("空白 header 视为没传，重新生成")
        void treatsBlankHeaderAsAbsent() throws Exception {
            MockHttpServletRequest request = new MockHttpServletRequest();
            request.addHeader(TraceIdHolder.HEADER, "   ");
            MockHttpServletResponse response = new MockHttpServletResponse();

            filter.doFilterInternal(request, response, mock(FilterChain.class));

            assertThat(response.getHeader(TraceIdHolder.HEADER))
                    .isNotBlank()
                    .isNotEqualTo("   ")
                    .hasSize(16);
        }

        @Test
        @DisplayName("生成格式与 Python 侧口径一致：16 位十六进制")
        void generatedIdMatchesPythonFormat() {
            assertThat(TraceIdHolder.generate()).matches("[0-9a-f]{16}");
        }
    }

    @Nested
    @DisplayName("MDC 生命周期")
    class MdcLifecycle {

        @Test
        @DisplayName("请求处理期间 MDC 里有 id，日志才能读到")
        void bindsTraceIdDuringChain() throws Exception {
            MockHttpServletRequest request = new MockHttpServletRequest();
            MockHttpServletResponse response = new MockHttpServletResponse();
            FilterChain chain = (req, res) -> assertThat(TraceIdHolder.current()).isNotBlank();

            filter.doFilterInternal(request, response, chain);
        }

        @Test
        @DisplayName("请求结束后清掉 —— 否则线程复用会污染下一个请求")
        void clearsAfterRequest() throws Exception {
            filter.doFilterInternal(new MockHttpServletRequest(), new MockHttpServletResponse(),
                    mock(FilterChain.class));

            assertThat(TraceIdHolder.current()).isNull();
        }

        @Test
        @DisplayName("业务抛异常时也要清理，不能把 id 泄漏出去")
        void clearsEvenOnException() throws Exception {
            FilterChain boom = (req, res) -> {
                throw new IllegalStateException("业务炸了");
            };

            try {
                filter.doFilterInternal(new MockHttpServletRequest(), new MockHttpServletResponse(), boom);
            } catch (IllegalStateException expected) {
                // 预期内：异常继续往上抛，我们只关心 MDC 有没有被清理
            }

            assertThat(TraceIdHolder.current()).isNull();
        }
    }
}
