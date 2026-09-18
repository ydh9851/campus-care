package com.campuscare.common;

import lombok.Getter;

/**
 * 业务异常：Service 层校验不通过时直接抛，由全局异常处理器统一转成 Result。
 */
@Getter
public class BizException extends RuntimeException {

    private final Integer code;

    public BizException(String message) {
        super(message);
        this.code = 1001;
    }

    public BizException(Integer code, String message) {
        super(message);
        this.code = code;
    }
}
