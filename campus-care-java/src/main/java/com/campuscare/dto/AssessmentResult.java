package com.campuscare.dto;

import com.campuscare.entity.AssessmentRecord;
import lombok.Data;

/**
 * 测评结果：记录本体 + 需要额外告诉前端的东西。
 */
@Data
public class AssessmentResult {

    /** 落库后的测评记录（含总分、严重程度、风险等级、答题明细） */
    private AssessmentRecord record;

    /** 量表满分，前端画进度条要用 */
    private Integer maxScore;

    /** 给出的处置建议文案（规则模板生成） */
    private String suggestion;

    /** 若本次触发了风险工单，这里是工单 id；否则为 null */
    private Long alertId;
}
