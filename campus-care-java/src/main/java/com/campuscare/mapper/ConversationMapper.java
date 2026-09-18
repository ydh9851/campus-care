package com.campuscare.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.campuscare.entity.Conversation;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Update;

/**
 * 会话 Mapper
 */
@Mapper
public interface ConversationMapper extends BaseMapper<Conversation> {

    /**
     * 一轮对话落库后：轮次 +1，并刷新风险等级（只升不降）。
     *
     * 两个写操作合并成一条 SQL，避免"先查后改"的丢失更新，也少一次数据库往返。
     * CASE 分支：HIGH 直接置高；MEDIUM 且当前不是 HIGH 则升级；其余保持原值。
     */
    @Update("""
            UPDATE conversation
            SET turn_count = turn_count + 1,
                risk_level = CASE
                    WHEN #{riskLevel} = 'HIGH' THEN 'HIGH'
                    WHEN #{riskLevel} = 'MEDIUM' AND risk_level <> 'HIGH' THEN 'MEDIUM'
                    ELSE risk_level END,
                update_time = NOW()
            WHERE id = #{conversationId}
            """)
    int increaseTurnCount(Long conversationId, String riskLevel);
}
