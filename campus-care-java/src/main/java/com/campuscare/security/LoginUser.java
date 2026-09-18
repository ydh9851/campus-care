package com.campuscare.security;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 登录用户上下文对象，解析 JWT 后放进 SecurityContext，
 * 后续业务通过 SecurityUtils.currentUser() 取用。
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class LoginUser {

    private Long userId;
    private String username;
    private String role;

    /** 是否管理员 */
    public boolean isAdmin() {
        return "ADMIN".equals(role);
    }

    /** 是否辅导员（可查看和处理风险预警） */
    public boolean isCounselor() {
        return "COUNSELOR".equals(role) || isAdmin();
    }
}
