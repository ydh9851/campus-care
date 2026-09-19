package com.campuscare.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.campuscare.entity.AccessLog;
import com.campuscare.mapper.AccessLogMapper;
import com.campuscare.security.LoginUser;
import com.campuscare.security.SecurityUtils;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

/**
 * 访问审计：记录辅导员对敏感数据的查阅与处置行为。
 *
 * 为什么必须有：心理档案属于敏感个人信息，出问题时（家长质疑、投诉、
 * 数据泄露排查）需要能回答「谁在什么时候看过这个学生的档案」。
 * 没有这张表，任何追责都无从谈起。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuditService {

    /** 查看学生心理档案 */
    public static final String VIEW_PROFILE = "VIEW_PROFILE";
    /** 处置风险工单 */
    public static final String HANDLE_ALERT = "HANDLE_ALERT";

    public static final String TARGET_USER = "USER";
    public static final String TARGET_ALERT = "ALERT";

    private final AccessLogMapper accessLogMapper;

    /**
     * 落一条审计。
     *
     * 刻意**不向外抛异常**：审计是旁路，日志写失败不该让辅导员连档案都打不开 ——
     * 那会把"合规加强"变成"系统不可用"。代价是理论上存在「访问成功但没留痕」的窗口，
     * 所以这里用 error 级别把问题喊出来，便于接监控告警。
     *
     * 若将来合规要求更严（审计即准入），应改成写不进审计就拒绝访问 ——
     * 但那是策略变更，需要显式决策，不该由这里默认决定。
     */
    public void record(String action, String targetType, Long targetId, String detail) {
        try {
            LoginUser operator = SecurityUtils.currentUserOrNull();
            AccessLog entity = new AccessLog();
            // operator_id 是 NOT NULL，理论上这里一定有登录用户；
            // 兜个 0 只是为了极端情况下日志行还能落库，不至于整条丢
            entity.setOperatorId(operator == null ? 0L : operator.getUserId());
            entity.setOperatorName(operator == null ? "anonymous" : operator.getUsername());
            entity.setAction(action);
            entity.setTargetType(targetType);
            entity.setTargetId(targetId);
            entity.setDetail(detail);
            entity.setIp(currentIp());
            accessLogMapper.insert(entity);
        } catch (Exception e) {
            log.error("写入访问审计失败（业务已放行）: action={}, target={}#{}, err={}",
                    action, targetType, targetId, e.getMessage());
        }
    }

    /** 审计日志分页查询，可按操作人、对象类型与对象 id 过滤 */
    public IPage<AccessLog> page(long current, long size, Long operatorId,
                                 String targetType, Long targetId) {
        return accessLogMapper.selectPage(
                new Page<>(current, size),
                Wrappers.<AccessLog>lambdaQuery()
                        .eq(operatorId != null, AccessLog::getOperatorId, operatorId)
                        .eq(StringUtils.hasText(targetType), AccessLog::getTargetType, targetType)
                        .eq(targetId != null, AccessLog::getTargetId, targetId)
                        .orderByDesc(AccessLog::getId));
    }

    /**
     * 取真实来源 IP。
     * 反向代理后面拿到的 remoteAddr 是网关自己的地址，所以优先看代理透传的头。
     * X-Forwarded-For 可能是「客户端, 代理1, 代理2」，只取第一段。
     */
    private String currentIp() {
        ServletRequestAttributes attrs =
                (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
        if (attrs == null) {
            return null;
        }
        HttpServletRequest request = attrs.getRequest();

        String forwarded = request.getHeader("X-Forwarded-For");
        if (StringUtils.hasText(forwarded)) {
            return forwarded.split(",")[0].trim();
        }
        String realIp = request.getHeader("X-Real-IP");
        if (StringUtils.hasText(realIp)) {
            return realIp;
        }
        return request.getRemoteAddr();
    }
}
