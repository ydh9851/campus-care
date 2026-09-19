package com.campuscare.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.campuscare.entity.AccessLog;
import org.apache.ibatis.annotations.Mapper;

/**
 * 访问审计日志 Mapper。
 * 只需要插入与分页查询，BaseMapper 足够，没有自定义 SQL。
 */
@Mapper
public interface AccessLogMapper extends BaseMapper<AccessLog> {
}
