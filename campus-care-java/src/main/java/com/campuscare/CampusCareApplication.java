package com.campuscare;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.security.servlet.UserDetailsServiceAutoConfiguration;

/**
 * CampusCare 校园心理多 Agent 智能咨询平台 - Java 主服务启动类。
 * 负责登录鉴权、会话管理、消息与风险记录落库，AI 推理请求转发给 Python 服务。
 *
 * exclude UserDetailsServiceAutoConfiguration：认证走自建的 JWT 过滤器，
 * 不需要自动配置的默认账号，否则启动日志会多出一行 generated security password。
 */
@SpringBootApplication(exclude = UserDetailsServiceAutoConfiguration.class)
@MapperScan("com.campuscare.mapper")
public class CampusCareApplication {

    public static void main(String[] args) {
        SpringApplication.run(CampusCareApplication.class, args);
        System.out.println("""
                ================================================
                  CampusCare Java 服务启动成功
                  接口文档: http://localhost:8080/swagger-ui.html
                ================================================
                """);
    }
}
