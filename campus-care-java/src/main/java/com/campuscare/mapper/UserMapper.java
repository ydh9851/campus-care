package com.campuscare.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.campuscare.entity.User;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

/**
 * 用户 Mapper。基础 CRUD 由 MyBatis-Plus BaseMapper 提供，
 * 复杂查询再手写 SQL 或 XML。
 */
@Mapper
public interface UserMapper extends BaseMapper<User> {

    /** 按账号查用户（登录用） */
    @Select("SELECT * FROM `user` WHERE username = #{username} LIMIT 1")
    User selectByUsername(String username);

    /** 统计某角色下的用户数（辅导员工作台用） */
    @Select("SELECT COUNT(*) FROM `user` WHERE role = #{role} AND status = 1")
    long countByRole(String role);
}
