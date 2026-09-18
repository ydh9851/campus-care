package com.campuscare.security;

import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.lang.NonNull;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * JWT 认证过滤器：
 * 1. 从请求头 Authorization: Bearer xxx 取出 token
 * 2. 校验签名 + 是否在 Redis 中（Redis 里没有说明已登出/被踢）
 * 3. 校验通过则把 LoginUser 放进 SecurityContext，并把角色转成 ROLE_xxx 权限
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtUtil jwtUtil;
    private final StringRedisTemplate redisTemplate;

    @Value("${jwt.header:Authorization}")
    private String header;

    @Value("${jwt.prefix:Bearer }")
    private String prefix;

    /** Redis key 前缀：login:token:{userId} -> token */
    public static final String TOKEN_KEY_PREFIX = "campuscare:login:token:";

    @Override
    protected void doFilterInternal(@NonNull HttpServletRequest request,
                                    @NonNull HttpServletResponse response,
                                    @NonNull FilterChain filterChain) throws ServletException, IOException {

        String token = resolveToken(request);
        if (StringUtils.hasText(token)) {
            Claims claims = jwtUtil.parseTokenQuietly(token);
            if (claims != null) {
                Long userId = Long.valueOf(claims.getSubject());
                // Redis 中不存在 → token 已失效（用户登出或超时）
                String cached = redisTemplate.opsForValue().get(TOKEN_KEY_PREFIX + userId);
                if (token.equals(cached)) {
                    String username = claims.get("username", String.class);
                    String role = claims.get("role", String.class);

                    LoginUser loginUser = new LoginUser(userId, username, role);
                    // 角色 -> Spring Security 权限，@PreAuthorize("hasRole('COUNSELOR')") 依赖这个前缀
                    List<SimpleGrantedAuthority> authorities =
                            List.of(new SimpleGrantedAuthority("ROLE_" + role));

                    UsernamePasswordAuthenticationToken authentication =
                            new UsernamePasswordAuthenticationToken(loginUser, null, authorities);
                    authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
                    SecurityContextHolder.getContext().setAuthentication(authentication);
                }
            }
        }
        filterChain.doFilter(request, response);
    }

    /** 从请求头解析 token */
    private String resolveToken(HttpServletRequest request) {
        String value = request.getHeader(header);
        if (!StringUtils.hasText(value)) {
            return null;
        }
        if (StringUtils.hasText(prefix) && value.startsWith(prefix)) {
            return value.substring(prefix.length()).trim();
        }
        return value.trim();
    }
}
