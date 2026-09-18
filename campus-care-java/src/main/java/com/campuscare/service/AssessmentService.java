package com.campuscare.service;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.campuscare.common.BizException;
import com.campuscare.common.RiskLevel;
import com.campuscare.dto.AssessmentResult;
import com.campuscare.dto.ScaleDetail;
import com.campuscare.dto.SubmitAssessmentRequest;
import com.campuscare.entity.AssessmentRecord;
import com.campuscare.mapper.AssessmentRecordMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 心理测评：计分 → 判定风险 → 落库 → 必要时建工单。分级规则来自量表定义文件。
 *
 * 除总分分级外还有一条单题高危规则：PHQ-9 第 9 题（自伤念头）只要不为 0 直接判 HIGH。
 * 因为总分会被其他题目稀释，这类学生按总分可能只是「轻度」，实际最需要干预。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AssessmentService {

    private final AssessmentRecordMapper assessmentRecordMapper;
    private final ScaleRegistry scaleRegistry;
    private final RiskAlertService riskAlertService;

    /** 量表列表（只给摘要，不带题目，避免列表接口传输一堆用不到的数据） */
    public List<Map<String, Object>> listScales() {
        List<Map<String, Object>> list = new ArrayList<>();
        for (ScaleDetail detail : scaleRegistry.all()) {
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("code", detail.getCode());
            item.put("name", detail.getName());
            item.put("intro", detail.getIntro());
            item.put("note", detail.getNote());
            item.put("maxScore", detail.getMaxScore());
            item.put("questionCount", detail.getQuestions() == null ? 0 : detail.getQuestions().size());
            list.add(item);
        }
        return list;
    }

    /** 量表详情：题目、选项、分级规则都给前端，前端据此渲染，不需要为量表写死界面 */
    public ScaleDetail getScale(String code) {
        return scaleRegistry.require(code);
    }

    /**
     * 提交作答。整个「校验 + 计分 + 写记录 + 建工单」是一个事务：
     * 要么都成功，要么都不留痕 —— 否则可能出现「有工单但查不到测评记录」这种对不上的数据。
     */
    @Transactional(rollbackFor = Exception.class)
    public AssessmentResult submit(Long userId, SubmitAssessmentRequest request) {
        ScaleDetail scale = scaleRegistry.require(request.getScaleCode());
        List<Integer> answers = request.getAnswers();

        validateAnswers(scale, answers);

        // ---------- 1. 计分 ----------
        int total = answers.stream().mapToInt(Integer::intValue).sum();

        // ---------- 2. 总分分级 ----------
        ScaleDetail.Level level = resolveLevel(scale, total);
        RiskLevel riskLevel = RiskLevel.of(level.getRiskLevel());

        // ---------- 3. 单题高危规则（会覆盖总分结论，只升不降） ----------
        List<String> criticalHits = new ArrayList<>();
        if (scale.getCriticalItems() != null) {
            for (ScaleDetail.CriticalItem item : scale.getCriticalItems()) {
                int index = item.getNo() - 1;
                if (index < 0 || index >= answers.size()) {
                    continue;
                }
                int minScore = item.getMinScore() == null ? 1 : item.getMinScore();
                if (answers.get(index) >= minScore) {
                    criticalHits.add(String.valueOf(item.getNo()));
                    riskLevel = RiskLevel.max(riskLevel, RiskLevel.of(item.getRiskLevel()));
                }
            }
        }

        // ---------- 4. 落库 ----------
        AssessmentRecord record = new AssessmentRecord();
        record.setUserId(userId);
        record.setScaleCode(scale.getCode());
        record.setScaleName(scale.getName());
        record.setTotalScore(total);
        record.setSeverity(level.getSeverity());
        record.setSeverityLabel(level.getLabel());
        record.setRiskLevel(riskLevel.name());
        record.setAnswers(answers.stream().map(String::valueOf).collect(Collectors.joining(",")));
        record.setHighRiskItems(criticalHits.isEmpty() ? null : String.join(",", criticalHits));
        assessmentRecordMapper.insert(record);

        // ---------- 5. 达到建单门槛就进统一工单池 ----------
        String suggestion = buildSuggestion(scale, record, riskLevel, criticalHits);
        Long alertId = riskAlertService.createAlert(new RiskAlertService.AlertDraft(
                userId,
                RiskAlertService.SOURCE_ASSESSMENT,
                null,
                null,
                record.getId(),
                riskLevel,
                buildAlertKeywords(scale, record, criticalHits),
                buildAlertContent(scale, record, criticalHits),
                suggestion));

        log.info("测评完成: userId={}, scale={}, total={}/{}, severity={}, riskLevel={}, alertId={}",
                userId, scale.getCode(), total, scale.getMaxScore(),
                record.getSeverityLabel(), riskLevel, alertId);

        AssessmentResult result = new AssessmentResult();
        result.setRecord(record);
        result.setMaxScore(scale.getMaxScore());
        result.setSuggestion(suggestion);
        result.setAlertId(alertId);
        return result;
    }

    /** 我的测评记录（按时间倒序） */
    public List<AssessmentRecord> myRecords(Long userId) {
        return assessmentRecordMapper.selectList(
                Wrappers.<AssessmentRecord>lambdaQuery()
                        .eq(AssessmentRecord::getUserId, userId)
                        .orderByDesc(AssessmentRecord::getId));
    }

    /** 某学生的测评记录（辅导员查看学生档案时用） */
    public List<AssessmentRecord> recordsOf(Long userId) {
        return myRecords(userId);
    }

    // ---------- 内部方法 ----------

    /** 校验题数与每题选项取值，避免非法分值把总分算爆 */
    private void validateAnswers(ScaleDetail scale, List<Integer> answers) {
        int expected = scale.getQuestions() == null ? 0 : scale.getQuestions().size();
        if (answers.size() != expected) {
            throw new BizException("答题数量不正确：应为 " + expected + " 题，实际 " + answers.size() + " 题");
        }
        Set<Integer> allowed = scale.getOptions().stream()
                .map(ScaleDetail.Option::getValue)
                .collect(Collectors.toSet());
        for (int i = 0; i < answers.size(); i++) {
            Integer value = answers.get(i);
            if (value == null || !allowed.contains(value)) {
                throw new BizException("第 " + (i + 1) + " 题的选项不合法");
            }
        }
    }

    /** 按总分落到第一个满足 total <= max 的区间 */
    private ScaleDetail.Level resolveLevel(ScaleDetail scale, int total) {
        for (ScaleDetail.Level level : scale.getLevels()) {
            if (level.getMax() != null && total <= level.getMax()) {
                return level;
            }
        }
        // 理论上不会发生（量表最后一档的 max 就是满分），兜底取最后一档
        return scale.getLevels().get(scale.getLevels().size() - 1);
    }

    /** 工单「关键词」列展示的内容：严重程度 + 高危题号 */
    private List<String> buildAlertKeywords(ScaleDetail scale, AssessmentRecord record, List<String> criticalHits) {
        List<String> keywords = new ArrayList<>();
        keywords.add(record.getSeverityLabel());
        for (String no : criticalHits) {
            keywords.add("第" + no + "题");
        }
        return keywords;
    }

    /** 工单「原文」列：量表没有原话，这里给一段可读的结论 */
    private String buildAlertContent(ScaleDetail scale, AssessmentRecord record, List<String> criticalHits) {
        StringBuilder sb = new StringBuilder();
        sb.append(scale.getName())
                .append("：总分 ").append(record.getTotalScore())
                .append("/").append(scale.getMaxScore())
                .append("（").append(record.getSeverityLabel()).append("）");
        if (!criticalHits.isEmpty()) {
            sb.append("，第 ").append(String.join("、", criticalHits)).append(" 题涉及自伤念头");
        }
        return sb.toString();
    }

    /**
     * 生成处置建议。用规则模板而不是 LLM：
     * 量表结论本身已标准化，不需要模型再解释一遍；且提交是同步接口，调 LLM 会明显拖慢响应。
     */
    private String buildSuggestion(ScaleDetail scale, AssessmentRecord record,
                                   RiskLevel riskLevel, List<String> criticalHits) {
        StringBuilder sb = new StringBuilder();
        sb.append("【").append(scale.getName()).append("：")
                .append(record.getSeverityLabel())
                .append("（总分 ").append(record.getTotalScore())
                .append("/").append(scale.getMaxScore()).append("）");
        if (!criticalHits.isEmpty()) {
            sb.append("，第 ").append(String.join("、", criticalHits)).append(" 题涉及自伤念头");
        }
        sb.append("】\n");

        if (riskLevel == RiskLevel.HIGH) {
            sb.append("建议：")
                    .append("1) 24 小时内安排一对一访谈，重点评估安全风险与支持系统（室友 / 家人 / 朋友）；")
                    .append("2) 转介学校心理中心做专业评估，必要时启动医校绿色通道；")
                    .append("3) 联系院系辅导员建立陪伴网络，避免学生长时间独处。");
        } else {
            sb.append("建议：")
                    .append("1) 3 个工作日内安排一次谈心，了解近期学业与人际压力；")
                    .append("2) 引导学生预约学校心理中心（在校生免费）；")
                    .append("3) 两周后复测一次，观察变化趋势。");
        }
        return sb.toString();
    }
}
