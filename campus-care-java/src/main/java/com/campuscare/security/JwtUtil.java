package com.campuscare.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

/**
 * JWT 工具类：签发与解析 token，密钥取配置项 jwt.secret（至少 32 字节）。
 *
 * 签名算法显式指定 HS256。jjwt 在 signWith(key) 不传算法时会按密钥长度自动选
 * （≥512 位选 HS512、≥384 位选 HS384），显式指定可避免将来改长密钥导致算法漂移、
 * 已签发的 token 全部失效。
 */
@Slf4j
@Component
public class JwtUtil {

    @Value("${jwt.secret}")
    private String secret;

    @Value("${jwt.expire-seconds}")
    private Long expireSeconds;

    private SecretKey signKey() {
        return Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    /**
     * 生成 token，把用户 id / 账号 / 角色放进 payload。
     */
    public String generateToken(Long userId, String username, String role) {
        Date now = new Date();
        Date expire = new Date(now.getTime() + expireSeconds * 1000);
        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claim("username", username)
                .claim("role", role)
                .issuedAt(now)
                .expiration(expire)
                .signWith(signKey(), Jwts.SIG.HS256)
                .compact();
    }

    /**
     * 解析 token。签名错误或过期会抛异常，由调用方捕获。
     */
    public Claims parseToken(String token) {
        return Jwts.parser()
                .verifyWith(signKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    /**
     * 安全解析：失败返回 null，不抛异常。
     */
    public Claims parseTokenQuietly(String token) {
        try {
            return parseToken(token);
        } catch (Exception e) {
            log.debug("token 解析失败: {}", e.getMessage());
            return null;
        }
    }

    /** token 距离过期还剩多少秒（用于 Redis 续期） */
    public long getRemainingSeconds(Claims claims) {
        long remain = (claims.getExpiration().getTime() - System.currentTimeMillis()) / 1000;
        return Math.max(remain, 0);
    }

    public Long getExpireSeconds() {
        return expireSeconds;
    }
}
