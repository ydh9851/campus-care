package com.campuscare.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import io.swagger.v3.oas.models.Components;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Swagger / OpenAPI 配置。访问 /swagger-ui.html
 */
@Configuration
public class OpenApiConfig {

    private static final String SCHEME = "Bearer";

    @Bean
    public OpenAPI campusCareOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("CampusCare 校园心理多 Agent 智能咨询平台 API")
                        .version("1.0.0")
                        .description("鉴权 / 会话 / 咨询 / 测评 / 风险预警 / 心理档案 / 数据看板")
                        .contact(new Contact().name("CampusCare 开发组").email("dev@campuscare.local")))
                // 右上角 Authorize 填入 Bearer token 后即可调试受保护接口
                .addSecurityItem(new SecurityRequirement().addList(SCHEME))
                .components(new Components().addSecuritySchemes(SCHEME,
                        new SecurityScheme()
                                .type(SecurityScheme.Type.HTTP)
                                .scheme("bearer")
                                .bearerFormat("JWT")));
    }
}
