package com.campuscare.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.campuscare.common.BizException;
import com.campuscare.dto.LoginRequest;
import com.campuscare.dto.LoginResponse;
import com.campuscare.dto.RegisterRequest;
import com.campuscare.entity.User;
import com.campuscare.mapper.UserMapper;
import com.campuscare.security.JwtUtil;
import com.campuscare.security.SecurityUtils;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;

import static com.campuscare.security.JwtAuthenticationFilter.TOKEN_KEY_PREFIX;

/**
 * 认证服务：注册 / 登录 / 登出 / 查当前用户。
 * BCrypt 存密码，JWT 签 token，Redis 存一份白名单用于主动失效。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;
    private final StringRedisTemplate redisTemplate;

    /** 注册，默认 STUDENT 角色 */
    @Transactional(rollbackFor = Exception.class)
    public Long register(RegisterRequest request) {
        Long exists = userMapper.selectCount(
                Wrappers.<User>lambdaQuery().eq(User::getUsername, request.getUsername()));
        if (exists != null && exists > 0) {
            throw new BizException("账号已存在");
        }

        User user = new User();
        user.setUsername(request.getUsername());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setRealName(request.getRealName());
        user.setStudentNo(request.getStudentNo());
        user.setPhone(request.getPhone());
        user.setEmail(request.getEmail());
        user.setRole("STUDENT");
        user.setStatus(1);

        userMapper.insert(user);
        log.info("新用户注册成功: id={}, username={}", user.getId(), user.getUsername());
        return user.getId();
    }

    /** 登录：校验密码 → 签发 JWT → 写 Redis 白名单 */
    public LoginResponse login(LoginRequest request) {
        User user = userMapper.selectByUsername(request.getUsername());
        // 账号不存在与密码错误返回同一句提示，避免账号枚举
        if (user == null) {
            throw new BizException("账号或密码错误");
        }
        if (user.getStatus() == null || user.getStatus() != 1) {
            throw new BizException("账号已被禁用，请联系管理员");
        }
        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new BizException("账号或密码错误");
        }

        String token = jwtUtil.generateToken(user.getId(), user.getUsername(), user.getRole());

        // key = campuscare:login:token:{userId}，TTL 与 token 有效期一致
        redisTemplate.opsForValue().set(
                TOKEN_KEY_PREFIX + user.getId(),
                token,
                Duration.ofSeconds(jwtUtil.getExpireSeconds()));

        log.info("用户登录成功: id={}, username={}, role={}", user.getId(), user.getUsername(), user.getRole());
        return new LoginResponse(token, user.getId(), user.getUsername(), user.getRealName(), user.getRole());
    }

    /** 登出：删掉 Redis 里的 token，token 立刻失效 */
    public void logout(Long userId) {
        redisTemplate.delete(TOKEN_KEY_PREFIX + userId);
        log.info("用户登出: id={}", userId);
    }

    /** 当前登录用户（不含密码） */
    public User currentUser() {
        Long userId = SecurityUtils.currentUserId();
        User user = userMapper.selectById(userId);
        if (user == null) {
            throw new BizException(401, "用户不存在");
        }
        user.setPassword(null);
        return user;
    }
}
