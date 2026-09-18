package com.campuscare.service;

import com.campuscare.common.BizException;
import com.campuscare.dto.ScaleDetail;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 量表注册表：启动时把 resources/scales/ 下的量表定义读进内存，避免每次请求读文件，
 * 也能在启动阶段就暴露 JSON 配置错误。
 * 新增量表：往 resources/scales/ 放一个 json，再到 SCALE_FILES 登记文件名。
 */
@Slf4j
@Component
public class ScaleRegistry {

    /** 需要加载的量表文件名（不带 .json）。按这个顺序展示。 */
    private static final List<String> SCALE_FILES = List.of("phq9", "gad7");

    private final Map<String, ScaleDetail> scales = new LinkedHashMap<>();

    public ScaleRegistry(ObjectMapper objectMapper) {
        for (String file : SCALE_FILES) {
            try (InputStream in = new ClassPathResource("scales/" + file + ".json").getInputStream()) {
                ScaleDetail detail = objectMapper.readValue(in, ScaleDetail.class);
                scales.put(detail.getCode(), detail);
                log.info("已加载量表: {} - {} ({} 题)",
                        detail.getCode(), detail.getName(),
                        detail.getQuestions() == null ? 0 : detail.getQuestions().size());
            } catch (Exception e) {
                // 启动就失败，别等到用户点开量表才发现配错了
                throw new IllegalStateException("加载量表定义失败: " + file, e);
            }
        }
    }

    /** 取量表定义，取不到直接抛业务异常 */
    public ScaleDetail require(String code) {
        ScaleDetail detail = scales.get(code == null ? "" : code.trim().toUpperCase());
        if (detail == null) {
            throw new BizException("量表不存在: " + code);
        }
        return detail;
    }

    /** 全部量表（返回同一份内存对象，调用方不要修改） */
    public List<ScaleDetail> all() {
        return new ArrayList<>(scales.values());
    }
}
