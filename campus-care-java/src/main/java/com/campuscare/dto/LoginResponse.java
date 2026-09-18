package com.campuscare.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 登录返回：token + 用户基本信息
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class LoginResponse {

    /** JWT，后续请求放在 header: Authorization: Bearer {token} */
    private String token;

    private Long userId;

    private String username;

    private String realName;

    /** STUDENT / COUNSELOR / ADMIN */
    private String role;
}
