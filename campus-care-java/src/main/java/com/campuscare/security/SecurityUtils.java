package com.campuscare.security;

import com.campuscare.common.BizException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

/**
 * 从 SecurityContext 里取当前登录用户的静态工具类。
 */
public final class SecurityUtils {

    private SecurityUtils() {
    }

    /** 取当前登录用户，未登录返回 null */
    public static LoginUser currentUserOrNull() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof LoginUser loginUser)) {
            return null;
        }
        return loginUser;
    }

    /** 取当前登录用户，未登录直接抛 401 */
    public static LoginUser currentUser() {
        LoginUser loginUser = currentUserOrNull();
        if (loginUser == null) {
            throw new BizException(401, "未登录或登录已过期");
        }
        return loginUser;
    }

    /** 取当前登录用户 id */
    public static Long currentUserId() {
        return currentUser().getUserId();
    }
}
