package com.campuscare.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.converter.StringHttpMessageConverter;
import org.springframework.web.client.RestTemplate;

import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * RestTemplate 配置：Java 服务调用 Python AI 服务用。
 * 两个超时都走 application.yml 的 {@code python.ai.*}，不在这里硬编码。
 */
@Configuration
public class RestTemplateConfig {

    /** 建立连接的超时（秒）：同机/同机房的服务，不需要给太长 */
    @Value("${python.ai.connect-timeout-seconds:5}")
    private int connectTimeoutSeconds;

    /**
     * 读取响应的超时（秒）：LLM 推理慢，必须给够。
     *
     * 这里必须读配置而不是写死。之前是硬编码 120s，而 application.yml 里的
     * {@code python.ai.timeout-seconds} 从来没被任何代码读过 ——
     * 「配置写了却不生效」比「根本没写配置」更危险：改配置的人会以为已经改成功了。
     */
    @Value("${python.ai.read-timeout-seconds:120}")
    private int readTimeoutSeconds;

    @Bean
    public RestTemplate restTemplate(RestTemplateBuilder builder) {
        RestTemplate restTemplate = builder
                .setConnectTimeout(Duration.ofSeconds(connectTimeoutSeconds))
                .setReadTimeout(Duration.ofSeconds(readTimeoutSeconds))
                .build();
        // 防止中文响应乱码
        restTemplate.getMessageConverters()
                .add(0, new StringHttpMessageConverter(StandardCharsets.UTF_8));
        return restTemplate;
    }
}
