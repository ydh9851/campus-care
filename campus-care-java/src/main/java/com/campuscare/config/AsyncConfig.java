package com.campuscare.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 异步任务线程池配置（目前只给 SSE 流式咨询用）。
 */
@Configuration
public class AsyncConfig {

    /**
     * SSE 专用线程池。
     * 不用 commonPool：SSE 任务会长时间阻塞，占满公共池会连累其他并行流。
     * 用守护线程，容器关闭时自动 shutdown。
     */
    @Bean(name = "sseExecutor", destroyMethod = "shutdown")
    public ExecutorService sseExecutor() {
        return Executors.newFixedThreadPool(16, runnable -> {
            Thread thread = new Thread(runnable, "sse-worker");
            thread.setDaemon(true);
            return thread;
        });
    }
}
