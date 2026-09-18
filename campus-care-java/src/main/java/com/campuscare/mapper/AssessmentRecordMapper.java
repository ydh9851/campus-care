package com.campuscare.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.campuscare.entity.AssessmentRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

/**
 * 心理测评记录 Mapper。基础 CRUD 由 BaseMapper 提供。
 */
@Mapper
public interface AssessmentRecordMapper extends BaseMapper<AssessmentRecord> {

    /** 某学生已完成的不同量表数量（用于档案页展示「测评覆盖情况」） */
    @Select("SELECT COUNT(DISTINCT scale_code) FROM assessment_record WHERE user_id = #{userId}")
    long countDistinctScaleByUser(Long userId);
}
