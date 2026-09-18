package com.campuscare.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.List;

/**
 * 提交测评作答。
 */
@Data
public class SubmitAssessmentRequest {

    @NotBlank(message = "量表编码不能为空")
    private String scaleCode;

    /**
     * 每题的选项分值，顺序与量表题目顺序一致，如 [1,2,0,3,...]。
     * 具体取值范围由量表定义里的 options 决定，服务端会校验。
     */
    @NotEmpty(message = "请完成全部题目")
    private List<Integer> answers;
}
