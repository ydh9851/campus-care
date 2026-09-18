package com.campuscare.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 用户表：学生 / 辅导员 / 管理员
 */
@Data
@TableName("user")
public class User implements Serializable {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 登录账号 */
    private String username;

    /** BCrypt 加密后的密码，永远不返回给前端 */
    @JsonIgnore
    private String password;

    /** 真实姓名 */
    private String realName;

    /** 学号 */
    private String studentNo;

    private String phone;

    private String email;

    /** STUDENT / COUNSELOR / ADMIN */
    private String role;

    /** 1 启用 0 禁用 */
    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
