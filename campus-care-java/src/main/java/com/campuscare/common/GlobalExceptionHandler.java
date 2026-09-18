package com.campuscare.common;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常处理。
 *
 * 状态码约定：401 / 403 用真实 HTTP 状态码，其余错误统一返回 HTTP 200 + body 中的 code。
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /** 业务异常 */
    @ExceptionHandler(BizException.class)
    public ResponseEntity<Result<Void>> handleBiz(BizException e) {
        log.warn("业务异常: {}", e.getMessage());
        return wrap(e.getCode(), e.getMessage());
    }

    /** @Valid 参数校验失败（RequestBody） */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValid(MethodArgumentNotValidException e) {
        FieldError fieldError = e.getBindingResult().getFieldError();
        String msg = fieldError == null ? "参数校验失败" : fieldError.getDefaultMessage();
        return Result.fail(400, msg);
    }

    /** 表单参数绑定失败 */
    @ExceptionHandler(BindException.class)
    public Result<Void> handleBind(BindException e) {
        FieldError fieldError = e.getBindingResult().getFieldError();
        String msg = fieldError == null ? "参数绑定失败" : fieldError.getDefaultMessage();
        return Result.fail(400, msg);
    }

    /** 权限不足（方法级 @PreAuthorize 拦截时走这里） */
    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<Result<Void>> handleAccessDenied(AccessDeniedException e) {
        log.warn("权限不足: {}", e.getMessage());
        return wrap(403, "无权限访问该资源");
    }

    /** 兜底 */
    @ExceptionHandler(Exception.class)
    public Result<Void> handleOther(Exception e) {
        log.error("系统异常", e);
        return Result.fail(500, "系统异常：" + e.getMessage());
    }

    /** 统一出口：401 / 403 映射为真实 HTTP 状态码，其余保持 200 */
    private ResponseEntity<Result<Void>> wrap(Integer code, String message) {
        HttpStatus status = switch (code == null ? 0 : code) {
            case 401 -> HttpStatus.UNAUTHORIZED;
            case 403 -> HttpStatus.FORBIDDEN;
            default -> HttpStatus.OK;
        };
        return ResponseEntity.status(status).body(Result.fail(code, message));
    }
}
