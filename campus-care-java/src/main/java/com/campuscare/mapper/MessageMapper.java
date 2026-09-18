package com.campuscare.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.campuscare.entity.Message;
import org.apache.ibatis.annotations.Mapper;

/**
 * 消息 Mapper
 */
@Mapper
public interface MessageMapper extends BaseMapper<Message> {
}
