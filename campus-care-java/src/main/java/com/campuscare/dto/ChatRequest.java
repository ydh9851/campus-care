package com.campuscare.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 发起心理咨询请求。
 * conversationId 不传 → 新建会话；传了 → 续聊该会话。
 */
@Data
@Schema(description = "咨询请求")
public class ChatRequest {

    @Schema(description = "会话 id，首次咨询留空即可")
    private Long conversationId;

    @NotBlank(message = "消息内容不能为空")
    @Schema(description = "学生说的话", example = "我最近总是失眠，感觉压力很大")
    private String content;
}
