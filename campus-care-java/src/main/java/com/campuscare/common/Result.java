package com.campuscare.common;

import lombok.Data;

import java.io.Serializable;

/**
 * 统一响应结果，所有接口固定返回 {code, message, data}。
 * code：200 成功 / 400 参数错误 / 401 未登录 / 403 无权限 / 500 服务端异常 / 1001 业务异常
 */
@Data
public class Result<T> implements Serializable {

    private Integer code;
    private String message;
    private T data;

    public Result() {
    }

    public Result(Integer code, String message, T data) {
        this.code = code;
        this.message = message;
        this.data = data;
    }

    /** 成功，带数据 */
    public static <T> Result<T> ok(T data) {
        return new Result<>(200, "success", data);
    }

    /** 成功，不带数据 */
    public static <T> Result<T> ok() {
        return new Result<>(200, "success", null);
    }

    /** 失败，默认业务异常码 1001 */
    public static <T> Result<T> fail(String message) {
        return new Result<>(1001, message, null);
    }

    /** 失败，自定义 code */
    public static <T> Result<T> fail(Integer code, String message) {
        return new Result<>(code, message, null);
    }
}
