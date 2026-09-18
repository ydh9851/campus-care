package com.campuscare.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

/**
 * 两个服务之间的统一信封：{code, message, data}
 */
@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class PyEnvelope<T> {

    private Integer code;

    private String message;

    private T data;

    public boolean isSuccess() {
        return code != null && code == 200;
    }
}
