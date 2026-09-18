package com.campuscare.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 传给 Python AI 服务的单条历史消息
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class HistoryMessage {

    /** user / assistant */
    private String role;

    private String content;
}
