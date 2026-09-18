/**
 * AI 回复的展示格式化。
 *
 * 模型返回的是 markdown（含 **加粗**、- 列表、### 标题）。
 * 这里不引 marked / dompurify，而是「先转义 HTML，再做极少量格式化」。
 * 顺序不能反：先转义能保证模型输出的任何内容都变不成可执行标签，
 * 天然免疫 XSS；而且少两个依赖，包也小。
 */
export function formatReply(raw) {
  if (!raw) return ''
  const escaped = String(raw)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  return escaped
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^#{1,4}\s*(.+)$/gm, '<strong>$1</strong>')
    .replace(/^[-*]\s+/gm, '· ')
    .replace(/\n{2,}/g, '<br><br>')
    .replace(/\n/g, '<br>')
}

/** 风险等级展示文案 */
export const RISK_LABEL = { HIGH: '高危', MEDIUM: '关注', LOW: '低风险' }

/** 意图展示文案 */
export const INTENT_LABEL = {
  PSYCH_EMOTION: '心理倾诉',
  KNOWLEDGE_QUERY: '知识查询',
  RISK_ALERT: '高危预警',
  CHITCHAT: '闲聊',
}

/** "2026-09-18 23:12:01" -> "23:12"；不是该格式就原样返回 */
export function hhmm(datetime) {
  if (!datetime) return ''
  const m = String(datetime).match(/(\d{2}):(\d{2})(?::\d{2})?$/)
  return m ? `${m[1]}:${m[2]}` : String(datetime)
}

/** "2026-09-18 23:12:01" -> "09-18 23:12" */
export function shortTime(datetime) {
  if (!datetime) return ''
  const m = String(datetime).match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : String(datetime)
}
