package com.campuscare.service;

import com.campuscare.common.BizException;
import com.campuscare.common.RiskLevel;
import com.campuscare.dto.AssessmentResult;
import com.campuscare.dto.SubmitAssessmentRequest;
import com.campuscare.entity.AssessmentRecord;
import com.campuscare.mapper.AssessmentRecordMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 测评计分单元测试。
 *
 * 为什么这个模块最该有测试：**它是全项目唯一"算错会害人"的逻辑**。
 * 档位边界差 1 分、或者第 9 题的单题高危规则失效，学生拿到的风险等级就是错的，
 * 而且界面上一切正常、没有任何报错 —— 工单不会建，辅导员不会收到通知。
 * 这类 bug 只有测试能拦住。
 *
 * 刻意使用**真实的 ScaleRegistry**（读 resources/scales/*.json），而不是手搓量表态：
 * 档位阈值本身就是配置，测试要守住的正是「配置文件里的数字」，
 * 用桩把配置绕过去，等于什么都没测。
 */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
@DisplayName("心理测评计分")
class AssessmentServiceTest {

    @Mock
    private AssessmentRecordMapper assessmentRecordMapper;

    @Mock
    private RiskAlertService riskAlertService;

    private AssessmentService service;

    private static final long USER_ID = 1L;

    @BeforeEach
    void setUp() {
        ScaleRegistry registry = new ScaleRegistry(new ObjectMapper());
        service = new AssessmentService(assessmentRecordMapper, registry, riskAlertService);
        when(riskAlertService.createAlert(any())).thenReturn(999L);
    }

    // ------------------------------------------------------------------
    // 构造作答的小工具
    // ------------------------------------------------------------------

    /** 全 0 作答（"完全没有"），长度 = 题数 */
    private List<Integer> zeros(int questions) {
        return new ArrayList<>(Collections.nCopies(questions, 0));
    }

    /**
     * 构造总分恰好为 total 的作答。
     * 每题最高 3 分，从第 1 题开始填，因此靠后的题（含第 9 题）保持 0 ——
     * 这正好让「总分分级」的测试不会被单题高危规则干扰。
     */
    private List<Integer> withTotal(int questions, int total) {
        List<Integer> answers = zeros(questions);
        int left = total;
        for (int i = 0; i < questions && left > 0; i++) {
            int value = Math.min(3, left);
            answers.set(i, value);
            left -= value;
        }
        assertThat(left).as("构造的作答无法凑出总分 %d", total).isZero();
        return answers;
    }

    private AssessmentResult submit(String scaleCode, List<Integer> answers) {
        SubmitAssessmentRequest request = new SubmitAssessmentRequest();
        request.setScaleCode(scaleCode);
        request.setAnswers(answers);
        return service.submit(USER_ID, request);
    }

    private AssessmentResult submitPhq9(List<Integer> answers) {
        return submit("PHQ9", answers);
    }

    private AssessmentResult submitGad7(List<Integer> answers) {
        return submit("GAD7", answers);
    }

    /**
     * 取本类传给建单入口的参数。
     *
     * 「等级不够就不建单」是 RiskAlertService 的职责（它内部会判 needAlert），
     * 所以这里不去断言 createAlert 的返回值，而是断言 AssessmentService 交给它的等级对不对 ——
     * 边界划在正确的地方，测试才不会被实现细节的变化搞红。
     */
    private RiskAlertService.AlertDraft capturedDraft() {
        ArgumentCaptor<RiskAlertService.AlertDraft> captor =
                ArgumentCaptor.forClass(RiskAlertService.AlertDraft.class);
        verify(riskAlertService, atLeastOnce()).createAlert(captor.capture());
        return captor.getValue();
    }

    // ==================================================================
    // 一、总分档位边界
    // ==================================================================

    @Nested
    @DisplayName("PHQ-9 总分档位（0-4 / 5-9 / 10-14 / 15-19 / 20-27）")
    class Phq9LevelBoundary {

        @Test
        @DisplayName("4 分仍属「无抑郁症状」，5 分才进入「轻度抑郁」")
        void boundary4And5() {
            AssessmentResult none = submitPhq9(withTotal(9, 4));
            assertThat(none.getRecord().getTotalScore()).isEqualTo(4);
            assertThat(none.getRecord().getSeverity()).isEqualTo("NONE");
            assertThat(none.getRecord().getSeverityLabel()).isEqualTo("无抑郁症状");
            assertThat(none.getRecord().getRiskLevel()).isEqualTo("LOW");

            AssessmentResult mild = submitPhq9(withTotal(9, 5));
            assertThat(mild.getRecord().getTotalScore()).isEqualTo(5);
            assertThat(mild.getRecord().getSeverity()).isEqualTo("MILD");
            assertThat(mild.getRecord().getRiskLevel()).isEqualTo("LOW");
        }

        @Test
        @DisplayName("9 分仍是轻度，10 分跨到中度并升为 MEDIUM")
        void boundary9And10() {
            assertThat(submitPhq9(withTotal(9, 9)).getRecord().getRiskLevel()).isEqualTo("LOW");

            AssessmentResult moderate = submitPhq9(withTotal(9, 10));
            assertThat(moderate.getRecord().getSeverity()).isEqualTo("MODERATE");
            assertThat(moderate.getRecord().getRiskLevel()).isEqualTo("MEDIUM");
        }

        @Test
        @DisplayName("14 分仍是中度，15 分跨到中重度并升为 HIGH")
        void boundary14And15() {
            assertThat(submitPhq9(withTotal(9, 14)).getRecord().getRiskLevel()).isEqualTo("MEDIUM");

            AssessmentResult severe = submitPhq9(withTotal(9, 15));
            assertThat(severe.getRecord().getSeverity()).isEqualTo("MODERATELY_SEVERE");
            assertThat(severe.getRecord().getRiskLevel()).isEqualTo("HIGH");
        }

        @Test
        @DisplayName("19 分是中重度，20 分是重度，两者都是 HIGH")
        void boundary19And20() {
            AssessmentResult a = submitPhq9(withTotal(9, 19));
            assertThat(a.getRecord().getSeverity()).isEqualTo("MODERATELY_SEVERE");
            assertThat(a.getRecord().getRiskLevel()).isEqualTo("HIGH");

            AssessmentResult b = submitPhq9(withTotal(9, 20));
            assertThat(b.getRecord().getSeverity()).isEqualTo("SEVERE");
            assertThat(b.getRecord().getRiskLevel()).isEqualTo("HIGH");
        }

        @Test
        @DisplayName("满分 27 落在最高档，不会越界")
        void fullScore() {
            AssessmentResult result = submitPhq9(withTotal(9, 27));
            assertThat(result.getRecord().getTotalScore()).isEqualTo(27);
            assertThat(result.getRecord().getSeverity()).isEqualTo("SEVERE");
            assertThat(result.getMaxScore()).isEqualTo(27);
        }

        @Test
        @DisplayName("全 0 作答是最低档，传给建单入口的等级是 LOW")
        void allZero() {
            AssessmentResult result = submitPhq9(zeros(9));
            assertThat(result.getRecord().getTotalScore()).isZero();
            assertThat(result.getRecord().getRiskLevel()).isEqualTo("LOW");
            assertThat(result.getRecord().getHighRiskItems()).isNull();

            RiskAlertService.AlertDraft draft = capturedDraft();
            assertThat(draft.riskLevel()).isEqualTo(RiskLevel.LOW);
            assertThat(draft.source()).isEqualTo(RiskAlertService.SOURCE_ASSESSMENT);
        }
    }

    // ==================================================================
    // 二、单题高危规则 —— 本文件里最重要的一组
    // ==================================================================

    @Nested
    @DisplayName("PHQ-9 第 9 题单题高危规则")
    class Phq9CriticalItem {

        @Test
        @DisplayName("第 9 题得 1 分 → 总分仅 1 分仍判 HIGH（总分会被稀释，这是设计意图）")
        void criticalItemOverridesLowTotal() {
            List<Integer> answers = zeros(9);
            answers.set(8, 1);   // 第 9 题 = 1（"好几天"）

            AssessmentResult result = submitPhq9(answers);

            // 总分只有 1 分，按档位表本该是「无抑郁症状 / LOW」
            assertThat(result.getRecord().getTotalScore()).isEqualTo(1);
            assertThat(result.getRecord().getSeverity()).isEqualTo("NONE");
            // 但单题规则把它拉到了 HIGH —— 这正是要守住的行为
            assertThat(result.getRecord().getRiskLevel())
                    .as("第 9 题不为 0 必须判 HIGH，否则最需要干预的学生会被漏掉")
                    .isEqualTo("HIGH");
            assertThat(result.getRecord().getHighRiskItems()).isEqualTo("9");

            // 判成 HIGH 只是一个字段，还必须真的以 HIGH 的等级进建单入口，工单才会被建出来
            assertThat(capturedDraft().riskLevel()).isEqualTo(RiskLevel.HIGH);
        }

        @Test
        @DisplayName("第 9 题得满分 3 分 → 同样判 HIGH 并记录题号")
        void criticalItemMaxScore() {
            List<Integer> answers = zeros(9);
            answers.set(8, 3);

            AssessmentResult result = submitPhq9(answers);

            assertThat(result.getRecord().getRiskLevel()).isEqualTo("HIGH");
            assertThat(result.getRecord().getHighRiskItems()).isEqualTo("9");
        }

        @Test
        @DisplayName("第 9 题为 0 → 不触发单题规则，即使总分到了中重度档")
        void criticalItemNotTriggeredWhenZero() {
            // 15 分 = 中重度档，本身就已是 HIGH；换个 MEDIUM 的分数更严格
            List<Integer> answers = withTotal(9, 12);
            assertThat(answers.get(8)).as("构造的作答应保持第 9 题为 0").isZero();

            AssessmentResult result = submitPhq9(answers);

            assertThat(result.getRecord().getRiskLevel()).isEqualTo("MEDIUM");
            assertThat(result.getRecord().getHighRiskItems()).isNull();
            assertThat(capturedDraft().riskLevel()).isEqualTo(RiskLevel.MEDIUM);
        }

        @Test
        @DisplayName("单题规则只升不降：总分已 HIGH 时不会因为第 9 题为 0 被降级")
        void criticalItemNeverDowngrades() {
            // 20 分 = 重度档 HIGH，第 9 题仍为 0
            AssessmentResult result = submitPhq9(withTotal(9, 20));
            assertThat(result.getRecord().getRiskLevel()).isEqualTo("HIGH");
            assertThat(result.getRecord().getHighRiskItems()).isNull();
        }

        @Test
        @DisplayName("命中单题规则时，工单内容里会带上具体题号")
        void criticalItemAppearsInSuggestion() {
            List<Integer> answers = zeros(9);
            answers.set(8, 2);

            AssessmentResult result = submitPhq9(answers);

            assertThat(result.getSuggestion()).contains("第 9 题").contains("自伤念头");
            assertThat(result.getSuggestion()).contains("24 小时内");
        }
    }

    // ==================================================================
    // 三、GAD-7（无单题高危配置，用于确认"没有 criticalItems 也能正常工作"）
    // ==================================================================

    @Nested
    @DisplayName("GAD-7 总分档位（0-4 / 5-9 / 10-14 / 15-21）")
    class Gad7LevelBoundary {

        @Test
        @DisplayName("4 分与 5 分是 LOW，两者之间只有分级标签变化")
        void boundary4And5() {
            AssessmentResult a = submitGad7(withTotal(7, 4));
            assertThat(a.getRecord().getSeverity()).isEqualTo("NONE");
            assertThat(a.getRecord().getRiskLevel()).isEqualTo("LOW");

            AssessmentResult b = submitGad7(withTotal(7, 5));
            assertThat(b.getRecord().getSeverity()).isEqualTo("MILD");
            assertThat(b.getRecord().getRiskLevel()).isEqualTo("LOW");
        }

        @Test
        @DisplayName("9 分是轻度，10 分跨到中度并升为 MEDIUM")
        void boundary9And10() {
            assertThat(submitGad7(withTotal(7, 9)).getRecord().getRiskLevel()).isEqualTo("LOW");

            AssessmentResult moderate = submitGad7(withTotal(7, 10));
            assertThat(moderate.getRecord().getSeverity()).isEqualTo("MODERATE");
            assertThat(moderate.getRecord().getRiskLevel()).isEqualTo("MEDIUM");
        }

        @Test
        @DisplayName("14 分是中度，15 分跨到重度并升为 HIGH")
        void boundary14And15() {
            assertThat(submitGad7(withTotal(7, 14)).getRecord().getRiskLevel()).isEqualTo("MEDIUM");

            AssessmentResult severe = submitGad7(withTotal(7, 15));
            assertThat(severe.getRecord().getSeverity()).isEqualTo("SEVERE");
            assertThat(severe.getRecord().getRiskLevel()).isEqualTo("HIGH");
        }

        @Test
        @DisplayName("GAD-7 没有高危题，任何分数都不会产生 highRiskItems")
        void noCriticalItemsConfigured() {
            assertThat(submitGad7(withTotal(7, 21)).getRecord().getHighRiskItems()).isNull();
        }
    }

    // ==================================================================
    // 四、入参校验 —— 拒绝非法分值把总分算爆
    // ==================================================================

    @Nested
    @DisplayName("作答校验")
    class Validation {

        @Test
        @DisplayName("题数不足 → 抛业务异常且提示应为几题")
        void tooFewAnswers() {
            assertThatThrownBy(() -> submitPhq9(zeros(8)))
                    .isInstanceOf(BizException.class)
                    .hasMessageContaining("9")
                    .hasMessageContaining("8");
        }

        @Test
        @DisplayName("题数过多 → 抛业务异常")
        void tooManyAnswers() {
            assertThatThrownBy(() -> submitPhq9(zeros(10)))
                    .isInstanceOf(BizException.class)
                    .hasMessageContaining("答题数量不正确");
        }

        @Test
        @DisplayName("选项取值超出 0-3 → 抛业务异常并指出题号")
        void invalidOptionValue() {
            List<Integer> answers = zeros(9);
            answers.set(2, 9);   // 第 3 题给个不存在的选项

            assertThatThrownBy(() -> submitPhq9(answers))
                    .isInstanceOf(BizException.class)
                    .hasMessageContaining("第 3 题");
        }

        @Test
        @DisplayName("含 null 作答 → 抛业务异常，而不是留下 NullPointerException")
        void nullAnswer() {
            List<Integer> answers = new ArrayList<>(Arrays.asList(0, 0, null, 0, 0, 0, 0, 0, 0));

            assertThatThrownBy(() -> submitPhq9(answers))
                    .isInstanceOf(BizException.class)
                    .hasMessageContaining("第 3 题");
        }

        @Test
        @DisplayName("量表不存在 → 抛业务异常")
        void unknownScale() {
            assertThatThrownBy(() -> submit("NOT_EXIST", zeros(9)))
                    .isInstanceOf(BizException.class)
                    .hasMessageContaining("量表不存在");
        }

        @Test
        @DisplayName("量表编码大小写不敏感（前端传小写也能working）")
        void scaleCodeCaseInsensitive() {
            AssessmentResult result = submit("phq9", withTotal(9, 12));
            assertThat(result.getRecord().getScaleCode()).isEqualTo("PHQ9");
        }
    }

    // ==================================================================
    // 五、落库内容
    // ==================================================================

    @Nested
    @DisplayName("记录落库")
    class Persistence {

        @Test
        @DisplayName("作答明细以逗号分隔存一行，长度与题数一致")
        void answersSerialized() {
            AssessmentResult result = submitPhq9(withTotal(9, 12));

            String answers = result.getRecord().getAnswers();
            assertThat(answers).isNotNull();
            assertThat(answers.split(",")).hasSize(9);
            // 逐题分值之和必须等于总分，防止序列化与计分用了两份数据
            int sum = Arrays.stream(answers.split(",")).mapToInt(Integer::parseInt).sum();
            assertThat(sum).isEqualTo(result.getRecord().getTotalScore());
        }

        @Test
        @DisplayName("记录带上了正确的用户 id 与量表名")
        void recordMetadata() {
            AssessmentResult result = submitPhq9(zeros(9));
            AssessmentRecord record = result.getRecord();
            assertThat(record.getUserId()).isEqualTo(USER_ID);
            assertThat(record.getScaleCode()).isEqualTo("PHQ9");
            assertThat(record.getScaleName()).contains("PHQ-9");
        }
    }
}
