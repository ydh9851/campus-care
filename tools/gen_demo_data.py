#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成演示数据 SQL（sql/demo_data.sql）。

为什么不用公开数据集？
  公开的中文心理对话数据集（如 PsyQA）是「求助 + 回复」的问答对，
  形状对不上本项目的表结构 —— 这边需要 conversation / message / risk_alert /
  consult_report / assessment_record 之间互相引用，并且满足几项一致性约束：
    1. conversation.turn_count 必须等于该会话实际的消息轮次；
    2. conversation.risk_level 必须等于该会话所有消息里的最高风险；
    3. risk_alert.message_id 必须指向触发预警的那条【学生】消息；
    4. 对话来源的工单 conversation_id/message_id 非空，量表来源的二者为空。
  问答对数据集无法直接满足这些约束，所以按真实分布生成。

用法：
    python tools/gen_demo_data.py            # 输出到 sql/demo_data.sql
使用：
    mysql -uroot -p campus_care < sql/demo_data.sql
"""
import os
import random
from datetime import datetime, timedelta

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sql", "demo_data.sql")

RANDOM_SEED = 20260919
DAYS_SPAN = 90
STUDENT_COUNT = 48

# 与 init.sql 中一致的 BCrypt 值，明文 123456
PWD = "$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iKTVKIUi"

SURNAMES = "王李张刘陈杨黄赵吴周徐孙马朱胡林郭何高罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘蒋"
GIVEN_1 = "晨曦宇轩浩然思远嘉怡雨欣梓涵俊杰明轩子墨语彤静怡佳琪"
GIVEN_2 = "婷悦萱瑶睿哲磊强丽娟薇琳露洋波峰超宁帆菲楠鑫岚洲"

MAJORS = ["计算机科学与技术", "软件工程", "电子信息工程", "自动化", "机械设计制造",
          "会计学", "工商管理", "汉语言文学", "英语", "应用心理学", "数学与应用数学",
          "临床医学", "土木工程", "环境工程", "视觉传达设计", "国际经济与贸易"]

TOPICS = [
    {
        "code": "EXAM",
        "intent": "PSYCH_EMOTION",
        "user": [
            "快到期末考试了，四门专业课堆在一起，感觉怎么复习都复习不完，每天都特别焦虑",
            "这次高数考砸了，感觉自己根本不是学这个的料，一想到期末就更慌",
            "考研倒计时不到两个月，做真题错一大半，晚上根本睡不着",
            "小组作业基本都是我一个人在做，又怕说出口影响关系，憋着很难受",
            "每次考试前都会心慌手抖，明明复习过了还是控制不住地紧张",
        ],
        "open": [
            "你把这么多压力一次性说出来，我听着都觉得沉。",
            "考试周把好几天的事情挤在一起，焦虑是很自然的反应。",
            "先谢谢你愿意讲这些。你不是不够努力，是这段时间的负荷确实太大了。",
        ],
        "advice": [
            "可以试着把待办拆成「今天只做三件」的小块：一门课的一个章节 + 一套错题 + 一次复盘。完成感会明显一些，也不容易因为看到整座山而泄气。",
            "把担心的事分成「可控」和「不可控」两栏，只处理可控那栏。比如「复习不完」不可控，但「今晚复习哪一章」可控。",
            "试试 4-7-8 呼吸法：吸气 4 秒、屏息 7 秒、呼气 8 秒，重复四轮。它不能消除焦虑，但能让心跳先降下来，好让你坐回书桌前。",
            "错题比新题重要。与其刷新题打击信心，不如把已经错的题重做一遍，把「不会」变成「会」，这种掌控感对情绪帮助很大。",
        ],
        "close": [
            "如果方便，可以告诉我你最担心的是哪一门，我们把它单独拆开看。",
            "这周你打算从哪一件小事开始？说说看，我陪你捋一遍。",
            "压力大的时候，记得吃饭和睡觉是底线，别拿它们换复习时间。",
        ],
    },
    {
        "code": "SLEEP",
        "intent": "PSYCH_EMOTION",
        "user": [
            "最近晚上总是睡不着，翻来覆去到两三点，白天上课完全没精神",
            "躺下之后脑子就开始不停地想事情，越想越清醒，特别痛苦",
            "作息完全乱了，早上起不来，晚上又睡不着，恶性循环",
            "已经连续一周睡不好了，白天头晕，什么都做不进去",
            "舍友睡得晚，灯一直亮着，我又不好意思说，只能熬着",
        ],
        "open": [
            "睡眠不好会连着影响情绪和注意力，你能注意到这件事本身很重要。",
            "躺下之后脑子停不下来，这种情况比「睡不着」更消耗人。",
            "听下来你这段时间真的挺累的。睡眠是很多问题的入口，我们先把这块理顺。",
        ],
        "advice": [
            "先固定起床时间，比固定入睡时间更有效。就算前一晚睡得晚，也尽量在同一时间起，让生物钟先稳下来。",
            "把「床上」和「睡觉」绑在一起：不要在床上刷手机、看书、想事情。躺 20 分钟还睡不着就起来坐一会儿，有困意再回去。",
            "睡前一小时把当天的念头写在纸上，写下来本身就相当于告诉自己「已经记下了，不用再反复想」。",
            "下午三点以后不碰咖啡因，包括奶茶和可乐。很多人不知道奶茶的咖啡因含量其实不低。",
        ],
        "close": [
            "你现在大概几点能躺下？我们从调整这个时间开始试试。",
            "如果两周之后还是这样，建议去校医院睡眠门诊看看，别硬扛。",
            "先试三晚，有任何变化都可以回来跟我说。",
        ],
    },
    {
        "code": "RELATION",
        "intent": "PSYCH_EMOTION",
        "user": [
            "和室友关系不太好，感觉被孤立了，回宿舍都觉得压抑",
            "在班里好像没有人真的把我当朋友，都是我主动，很累",
            "我性格比较内向，一到大场合就说不出话，事后又特别懊恼",
            "被最好的朋友误会了，我解释了她也不听，心里特别堵",
            "社团里我说话好像总是没人接，慢慢就不想去了",
        ],
        "open": [
            "被孤立的感觉很具体，也很疼，这不是你想多了。",
            "主动的人往往最累，因为付出和回应不总是对等的。",
            "人际里的委屈很难说清楚，能讲出来已经不容易了。",
        ],
        "advice": [
            "可以先把「关系」缩小到一两个人。不需要让所有人都喜欢你，有一两个能说真话的人就足够支撑很多。",
            "试着把感受说成「我」的句式：「我最近有点插不上话」，比「你们都不理我」更容易被接住，也不容易变成争吵。",
            "如果宿舍氛围确实影响休息，可以考虑找辅导员聊聊调宿的可能，这不是逃避，是给自己换一个能喘气的环境。",
            "内向不是缺陷。你的优势可能是倾听和深度交流，不必强迫自己变成场合里最活跃的那个人。",
        ],
        "close": [
            "宿舍里有没有相对好说话的那一个？也许可以从他开始。",
            "你希望这段关系变成什么样？我们可以一起想想第一步。",
            "被误会的时候，先照顾自己的情绪，再考虑要不要继续解释。",
        ],
    },
    {
        "code": "LOVE",
        "intent": "PSYCH_EMOTION",
        "user": [
            "分手快一个月了，一直缓不过来，看到她的消息还是会心跳加速",
            "异地恋坚持了一年多，最近他总是敷衍我，我不知道要不要继续",
            "喜欢一个人很久了，但对方好像完全没感觉，每天都很煎熬",
            "我们在同一个班，分手了还要天天见面，特别难受",
            "感觉自己在这段关系里一直在退让，越来越不像自己了",
        ],
        "open": [
            "一段关系结束后难受是正常的，不需要逼自己快点好起来。",
            "你说「越来越不像自己」，这句话很值得停一下 —— 能意识到这点说明你其实看得很清楚。",
            "感情里的消耗是慢性的，你能讲出来，说明已经在往外走了。",
        ],
        "advice": [
            "失恋的难受有生理基础，和戒断反应类似，通常几周后强度会自然下降。这段时间别用「我是不是太脆弱」来责备自己。",
            "先做「物理隔离」：把聊天窗口折叠、必要的联系方式留一条就够。反复看记录会让恢复期拖长。",
            "把注意力放回具体的日常上：一顿饭、一次跑步、一次和朋友的见面。情绪没法靠想通解决，但可以靠生活重新填满。",
            "如果是「要不要继续」这类选择，可以写下继续和分开各自的代价，写下来往往比在心里翻来覆去清楚得多。",
        ],
        "close": [
            "这一个月你都是怎么过的？有没有哪一天稍微好一点？",
            "不用急着做决定，先把这周过稳。",
            "如果影响到了吃饭睡觉，我们再把节奏调一调。",
        ],
    },
    {
        "code": "FAMILY",
        "intent": "PSYCH_EMOTION",
        "user": [
            "爸妈总是拿我跟表姐比，每次打电话都要吵，现在都不敢接电话了",
            "家里希望我考公务员，但我想做设计，一提就闹僵",
            "父母感情不好，每次放假回家都要处理他们的情绪，很累",
            "从小被要求「懂事」，现在好像连自己想要什么都不知道了",
            "家里经济压力大，我不敢跟他们说我在学校也很吃力",
        ],
        "open": [
            "家里本该是能歇脚的地方，但有时候恰恰相反，这种落差很消耗人。",
            "被反复比较是很难受的，尤其是来自最亲近的人。",
            "「懂事」这个词有时候是负担，你已经背了很久了。",
        ],
        "advice": [
            "和父母的沟通可以降低目标：不追求说服他们，只求把话说完。比如「我知道你们是为我好，但我想先按自己的想法试一年」。",
            "给家里打电话前设一个时长上限，比如先聊十分钟日常，超出部分不进入争论话题。把边界做出来，比硬扛有效。",
            "家庭的情绪不是你的责任。你可以关心他们，但不需要替他们承担关系里的问题。",
            "在校期间可以多利用学校的资源：导师、辅导员、心理咨询中心，把支持系统从家庭扩展到外部。",
        ],
        "close": [
            "最近一次和家里通电话是什么时候？当时的感受还记得吗？",
            "有没有哪个家里人是你觉得相对能说上话的？",
            "先照顾好自己，这不是自私。",
        ],
    },
    {
        "code": "CAREER",
        "intent": "PSYCH_EMOTION",
        "user": [
            "秋招投了六十多份简历，面试只有三次，感觉自己很差劲",
            "身边的同学都拿到 offer 了，我还在等消息，每天都在自我怀疑",
            "不知道自己适合做什么，专业也不喜欢，很迷茫",
            "实习的时候被领导当众批评，现在一想到上班就发怵",
            "考研和找工作两条路都在准备，结果两边都做不好",
        ],
        "open": [
            "投递和面试阶段的反馈周期长，很容易把「还没消息」误解成「我不行」。",
            "看到同学先有结果，会产生很强的比较压力，这很正常。",
            "迷茫本身不可怕，可怕的是逼自己在迷茫里立刻给出答案。",
        ],
        "advice": [
            "把「找工作」拆成可控动作：每天改一版简历、投 5 家、复盘 1 场面试。用一个能打勾的清单替代「有没有 offer」这个你无法控制的结果指标。",
            "面试被拒往往和岗位匹配度有关，不完全是能力问题。可以记录每场面试被问住的问题，它们比简历更能指出该补什么。",
            "「不知道适合什么」可以先用排除法：列出你确定不想做的，范围缩小之后再谈方向。",
            "两条路同时准备容易两边都浅。可以给自己定一个主次，比如主投递、副备考，别让两个目标互相拉扯。",
        ],
        "close": [
            "目前手上有在推进的流程吗？我们可以一起看看卡在哪一环。",
            "你投递的方向大概集中吗？还是有点散？",
            "这段时间先保证睡够，面试状态和睡眠直接相关。",
        ],
    },
    {
        "code": "SELFD",
        "intent": "PSYCH_EMOTION",
        "user": [
            "总觉得自己什么都做不好，别人随口一句话我都能想很久",
            "我好像特别在意别人的评价，一被否定就整个人塌下去",
            "明明知道不该这么想，但就是控制不住地否定自己",
            "在人群里总觉得自己是最差的那个，不太敢说话",
            "做事情之前总要先想很久别人会怎么看我",
        ],
        "open": [
            "能这样描述自己，说明你对自己的状态有很清楚的觉察。",
            "对评价敏感的人，往往对他人也很体贴 —— 这两件事常常是一起的。",
            "「控制不住地否定自己」是很消耗的，这不是意志力的问题。",
        ],
        "advice": [
            "试着记录「事实」和「想法」两列。比如事实是「这次报告被指出三个问题」，想法是「我什么都做不好」。分开写之后，会发现想法往往跳得比事实远。",
            "自我否定常常来自一套很严的标准。可以问问自己：如果朋友遇到同样的事，你会用这句话对他说吗？",
            "每天写下一件「做到了的小事」，哪怕只是按时起床。这不是自我安慰，是在补上一直被忽略的证据。",
            "如果这种否定持续影响睡眠、食欲或者社交，建议到校心理中心做一次面谈，有人陪着梳理会快很多。",
        ],
        "close": [
            "有没有哪一次，你其实做得不错，但当时没允许自己承认？",
            "你觉得这套标准最早是从哪里来的？",
            "先从记录一周开始，我们下次一起看。",
        ],
    },
    {
        "code": "MOOD",
        "intent": "PSYCH_EMOTION",
        "user": [
            "最近对什么都提不起兴趣，以前喜欢的事现在也不想做了",
            "情绪一直很低，也说不上具体因为什么，就是开心不起来",
            "每天都觉得很累，睡很久还是没力气",
            "不太想跟人说话，只想一个人待着",
            "有时候会突然很难过，在教室都想哭",
        ],
        "open": [
            "持续的低落和兴趣减退，是值得认真对待的信号，不是「想开点」就能过去的。",
            "说不上原因的低落确实更难处理，因为它没有可以对着解决的靶子。",
            "你能把这种状态描述出来，我听到了，也认真对待。",
        ],
        "advice": [
            "先保住最基本的几件事：规律吃饭、尽量出门、每天见一点阳光。情绪低的时候，能维持日常本身就是成果。",
            "把目标降到「最小可执行」：不是「去运动」，而是「下楼走五分钟」。做到了再谈加量。",
            "低谷期不适合做重大决定，比如退学、分手、辞职。可以先把想法记下来，等状态回升再回头看。",
            "如果这种状态持续两周以上，并且影响到上课和人际，建议到校心理中心或医院精神科做一次评估，这是常规操作，不必有负担。",
        ],
        "close": [
            "这种状态大概持续多久了？一个月还是更久？",
            "这周有没有哪一刻稍微轻一点？哪怕很短。",
            "不管怎样，先别一个人扛。",
        ],
    },
    {
        "code": "KNOW",
        "intent": "KNOWLEDGE_QUERY",
        "user": [
            "考试焦虑有什么科学的缓解方法吗？",
            "怎么样才能改善睡眠质量？",
            "情绪低落的时候有什么自助的方法？",
            "怎么判断自己是不是抑郁了？",
            "有什么方法可以缓解社交紧张？",
        ],
        "open": [
            "这个问题很具体，我从有依据的方法说起。",
            "可以，先给你几条研究支持比较充分的做法。",
            "好，这类问题有比较成熟的自助思路。",
        ],
        "advice": [
            "认知行为疗法里的「想法记录」性价比很高：写下情境、自动冒出的念头、情绪强度，再写一条更贴近事实的替代想法。坚持两周通常能感到差别。",
            "行为激活是改善低落情绪最直接的方法之一：不等有动力才行动，而是先安排小行动，动力往往跟着行为来。",
            "放松训练里，渐进式肌肉放松和呼吸训练的证据最充分。每天十分钟，比偶尔做一次一小时更有效。",
            "评估自己的状态时，重点看三件事：持续时间、对学习生活的影响程度、有没有自伤念头。前两项能自查，第三项需要专业评估。",
        ],
        "close": [
            "需要的话我可以按你的情况把步骤再拆细一点。",
            "这些方法都适合自助，但如果两周没改善，建议找咨询师。",
            "你想先从哪一条开始？",
        ],
    },
    {
        "code": "CHAT",
        "intent": "CHITCHAT",
        "user": ["你好", "在吗", "今天天气不错", "随便聊聊", "你是什么"],
        "open": [
            "我在。",
            "你好，我在这里。",
            "嗯，我在听。",
        ],
        "advice": [
            "今天过得怎么样？有没有什么想说的？学习、生活、或者只是随便聊聊都可以。",
            "有什么想聊的都可以说，没有主题也没关系。",
        ],
        "close": [
            "",
            "慢慢说，不着急。",
        ],
    },
]

HIGH_RISK_UTTER = [
    "我觉得活着没什么意思，有时候会想消失掉算了",
    "最近老是想着要是没有我，大家可能会轻松一点",
    "有几次站在阳台上会想，如果掉下去是不是就结束了",
    "我会用手掐自己，看到痕迹的时候反而会平静一点",
    "感觉撑不下去了，想结束这一切",
    "每天醒来第一个念头就是不想活了",
]

HIGH_RISK_KEYWORDS = {
    "我觉得活着没什么意思，有时候会想消失掉算了": "活着没意思,消失",
    "最近老是想着要是没有我，大家可能会轻松一点": "没有我,轻松一点",
    "有几次站在阳台上会想，如果掉下去是不是就结束了": "阳台,结束",
    "我会用手掐自己，看到痕迹的时候反而会平静一点": "掐自己,痕迹",
    "感觉撑不下去了，想结束这一切": "撑不下去,结束",
    "每天醒来第一个念头就是不想活了": "不想活",
}

HIGH_RISK_REPLY = (
    "听到你这么说，我很担心你。你愿意说出来，这需要很大的勇气，谢谢你信任我。\n\n"
    "我想先确认一件事：**你现在是安全的吗？** 有没有正在做的、或者已经计划好的伤害自己的事？\n\n"
    "请现在就联系能马上帮到你的人，不要一个人扛：\n"
    "- **学校心理健康教育中心**（工作日可预约面谈）\n"
    "- **全国24小时心理援助热线：400-161-9995**\n"
    "- **北京心理危机研究与干预中心：010-82951332**\n"
    "- 情况紧急时请直接拨打 **120** 或 **110**\n\n"
    "你现在的痛苦是真实的，但它不等于永远。我这边也已经把这个情况同步给了学校心理中心的老师，"
    "他们会在了解情况后与你联系。在那之前，请尽量待在有人陪伴的地方。"
)

ASSESS_TYPES = [
    {
        "code": "PHQ9", "name": "PHQ-9 抑郁症筛查量表", "count": 9, "max_score": 27,
        "levels": [(0, 4, "NONE", "无抑郁症状"), (5, 9, "MILD", "轻度抑郁"),
                   (10, 14, "MODERATE", "中度抑郁"), (15, 19, "MODERATELY_SEVERE", "中重度抑郁"),
                   (20, 27, "SEVERE", "重度抑郁")],
        "high_cut": 15, "medium_cut": 10, "critical_item": 8,  # 第 9 题下标（0-based）
    },
    {
        "code": "GAD7", "name": "GAD-7 广泛性焦虑量表", "count": 7, "max_score": 21,
        "levels": [(0, 4, "NONE", "无焦虑症状"), (5, 9, "MILD", "轻度焦虑"),
                   (10, 14, "MODERATE", "中度焦虑"), (15, 21, "SEVERE", "重度焦虑")],
        "high_cut": 15, "medium_cut": 10, "critical_item": None,
    },
]

REPORT_SUMMARY = {
    "LOW": [
        "本次会话中，学生主要围绕{s}进行倾诉，情绪状态整体平稳，反馈积极，已给出针对性的自我调节建议，暂无需人工介入。",
        "学生主动讨论了{s}，表达过程中情绪较为稳定，对建议接受度良好，建议保持自主调节。",
    ],
    "MEDIUM": [
        "本次会话中，学生主要表达了{s}，情绪波动较明显，存在一定程度的困扰。已提供情绪管理与求助渠道建议，建议辅导员在 3 个工作日内关注其状态变化。",
        "学生围绕{s}展开叙述，呈现出持续性的压力反应，自评情绪偏低。建议安排一次简短谈心，确认其支持系统是否完整。",
    ],
    "HIGH": [
        "本次会话出现自伤或轻生相关表达，风险等级判为高危，已即时推送危机干预资源并生成工单。学生主诉{s}，建议辅导员与心理中心在 24 小时内介入，确认其安全状况并建立陪伴机制。",
        "会话中识别到危机信号，学生主诉{s}，情绪评分极低，已提供 24 小时援助热线。建议立即启动危机干预流程，联系其身边可信任的同学或家人。",
    ],
}

REPORT_SUGGEST = {
    "LOW": "保持关注即可。可在班级日常活动中自然了解学生的近况，无需特别干预。",
    "MEDIUM": "建议辅导员在一周内安排一次非正式谈话，了解压力来源与睡眠情况，必要时转介校心理中心。",
    "HIGH": "立即启动危机干预流程：安排辅导员或心理中心老师当面联系学生确认安全状况，联系可信任的同学或室友建立短期监护，并在 24 小时内完成首次跟进记录。",
}

ASSESS_ALERT_CONTENT = "{name}测评结果为「{label}」，总分 {score}/{max} 分{extra}。"

HANDLE_REMARKS = [
    "已当面谈过一次，学生情绪较之前平稳，约定两周后回访。",
    "联系了学生本人与室友，确认目前安全，已转介校心理中心。",
    "已与家长电话沟通，家长知情并表示配合，安排每周一次跟进。",
    "学生自评分下降，已纳入重点关注名单，持续观察。",
    "经了解为考试阶段性的情绪波动，已提供调节建议并告知求助渠道。",
    "已完成首次危机干预面谈，学生同意接受持续辅导。",
]

COUNSELORS = [
    ("teacher01", "陈书棠", None),
    ("teacher02", "沈砚", None),
    ("teacher03", "顾云舒", None),
]


def pick_name(rnd):
    return rnd.choice(SURNAMES) + rnd.choice(GIVEN_1) + (rnd.choice(GIVEN_2) if rnd.random() < 0.55 else "")


def sql_str(text):
    if text is None:
        return "NULL"
    return "'" + str(text).replace("\\", "\\\\").replace("'", "''") + "'"


def sql_str_or_null(text):
    return "NULL" if text in (None, "") else sql_str(text)


def make_reply(rnd, topic):
    parts = [rnd.choice(topic["open"]), rnd.choice(topic["advice"])]
    close = rnd.choice(topic["close"])
    if close:
        parts.append(close)
    return "\n\n".join(parts)


def assess_level(cfg, score):
    for lo, hi, code, label in cfg["levels"]:
        if lo <= score <= hi:
            return code, label
    return cfg["levels"][-1][2], cfg["levels"][-1][3]


def assess_risk(cfg, score, answers):
    if score >= cfg["high_cut"]:
        return "HIGH"
    if cfg["critical_item"] is not None and answers[cfg["critical_item"]] > 0:
        return "HIGH"
    if score >= cfg["medium_cut"]:
        return "MEDIUM"
    return "LOW"


def main():
    rnd = random.Random(RANDOM_SEED)
    now = datetime.now().replace(microsecond=0)

    lines = []
    add = lines.append

    add("-- ============================================================")
    add("-- CampusCare 演示数据（由 tools/gen_demo_data.py 生成，请勿手改）")
    add("-- 导入：mysql -uroot -p campus_care < sql/demo_data.sql")
    add("-- 说明：会清空业务表后重建，保留 student01 / teacher01 账号")
    add("-- ============================================================")
    add("USE campus_care;")
    add("")
    add("SET NAMES utf8mb4;")
    add("")
    add("DELETE FROM `risk_alert`;")
    add("DELETE FROM `consult_report`;")
    add("DELETE FROM `message`;")
    add("DELETE FROM `conversation`;")
    add("DELETE FROM `assessment_record`;")
    add("DELETE FROM `user` WHERE `username` NOT IN ('student01', 'teacher01');")
    add("")
    add("ALTER TABLE `risk_alert` AUTO_INCREMENT = 1;")
    add("ALTER TABLE `consult_report` AUTO_INCREMENT = 1;")
    add("ALTER TABLE `message` AUTO_INCREMENT = 1;")
    add("ALTER TABLE `conversation` AUTO_INCREMENT = 1;")
    add("ALTER TABLE `assessment_record` AUTO_INCREMENT = 1;")
    add("")
    add("UPDATE `user` SET `real_name` = '陈书棠' WHERE `username` = 'teacher01';")
    add("UPDATE `user` SET `real_name` = '林思远', `student_no` = '2022010138',")
    add("  `phone` = '13800000001', `email` = 'lin.sy@campus.edu.cn' WHERE `username` = 'student01';")
    add("")

    # ---------- 用户 ----------
    user_rows = []
    uid = 3
    counselor_ids = [2]
    for username, real_name, _ in COUNSELORS[1:]:
        user_rows.append((uid, username, real_name, None, "COUNSELOR"))
        counselor_ids.append(uid)
        uid += 1
    admin_id = uid
    user_rows.append((uid, "admin", "系统管理员", None, "ADMIN"))
    uid += 1

    students = []
    used_names = set()
    for i in range(STUDENT_COUNT):
        name = pick_name(rnd)
        while name in used_names:
            name = pick_name(rnd)
        used_names.add(name)
        year = rnd.choice([2022, 2023, 2024, 2025])
        student_no = "%d%04d%03d" % (year, rnd.randint(1, 30), rnd.randint(1, 260))
        username = "stu%04d" % (1000 + i)
        phone = "1%d%09d" % (rnd.choice([3, 5, 7, 8, 9]), rnd.randint(0, 999999999))
        email = "%s@campus.edu.cn" % username
        create = now - timedelta(days=rnd.randint(DAYS_SPAN, DAYS_SPAN + 400))
        students.append({
            "id": uid, "username": username, "real_name": name, "student_no": student_no,
            "phone": phone, "email": email, "create": create,
        })
        user_rows.append((uid, username, name, student_no, "STUDENT"))
        uid += 1

    # student01 也当作一个正常学生参与数据生成
    students.append({
        "id": 1, "username": "student01", "real_name": "林思远", "student_no": "2022010138",
        "phone": "13800000001", "email": "lin.sy@campus.edu.cn",
        "create": now - timedelta(days=DAYS_SPAN + 120),
    })

    add("-- ---------------- 用户 ----------------")
    add("INSERT INTO `user` (`id`, `username`, `password`, `real_name`, `student_no`, `phone`, `email`, `role`, `create_time`) VALUES")
    rows = []
    for u, username, real_name, student_no, role in user_rows:
        rows.append("  (%d, %s, %s, %s, %s, %s, %s, %s, %s)"
                    % (u, sql_str(username), sql_str(PWD), sql_str(real_name),
                       sql_str_or_null(student_no),
                       sql_str("1%d%09d" % (rnd.choice([3, 5, 7, 8, 9]), rnd.randint(0, 999999999))) if role == "STUDENT" else "NULL",
                       sql_str("%s@campus.edu.cn" % username),
                       sql_str(role),
                       sql_str((now - timedelta(days=rnd.randint(DAYS_SPAN, DAYS_SPAN + 400))).strftime("%Y-%m-%d %H:%M:%S"))))
    add(",\n".join(rows) + ";")
    add("")

    # ---------- 会话 / 消息 ----------
    conv_rows = []
    msg_rows = []
    alert_rows = []
    report_rows = []

    conv_id = 1
    msg_id = 1
    alert_id = 1
    report_id = 1

    for stu in students:
        # 约 15% 的学生是「沉默用户」，一次都没咨询过
        if rnd.random() < 0.13:
            continue
        conv_n = rnd.choices([1, 2, 3, 4, 5, 6, 8], weights=[13, 19, 21, 16, 13, 11, 7])[0]
        # 学生活跃度分层：一部分学生更容易出现高危会话
        risk_prone = rnd.random() < 0.25

        for _ in range(conv_n):
            start_day = rnd.randint(0, DAYS_SPAN - 1)
            conv_time = (now - timedelta(days=start_day, hours=rnd.randint(0, 23),
                                         minutes=rnd.randint(0, 59)))
            if conv_time > now:
                conv_time = now - timedelta(minutes=rnd.randint(20, 300))

            turn_n = rnd.choices([1, 2, 3, 4, 5], weights=[14, 22, 25, 22, 17])[0]

            # 时段分布：重点风险学生更倾向深夜倾诉，其余学生集中在白天课间与晚间
            if risk_prone:
                hours = [0, 1, 2, 3, 20, 21, 22, 23, 10, 15, 16]
                hour_w = [10, 9, 6, 3, 5, 7, 12, 13, 3, 3, 3]
            else:
                hours = [9, 10, 11, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23, 0, 1]
                hour_w = [5, 6, 5, 5, 7, 7, 6, 5, 6, 5, 4, 4, 3, 2, 1]
            conv_time = conv_time.replace(hour=rnd.choices(hours, weights=hour_w)[0])

            high_p = 0.16 if risk_prone else 0.05
            med_p = 0.34 if risk_prone else 0.20

            conv_messages = []
            conv_max_risk = "LOW"
            conv_high_alert_msg = None
            title = None
            t = conv_time

            for turn in range(turn_n):
                t = t + timedelta(minutes=rnd.randint(3, 90))

                roll = rnd.random()
                if roll < high_p:
                    topic = None
                    user_text = rnd.choice(HIGH_RISK_UTTER)
                    intent = "RISK_ALERT"
                    risk = "HIGH"
                    reply = HIGH_RISK_REPLY
                    keywords = HIGH_RISK_KEYWORDS.get(user_text, "")
                else:
                    pool = [x for x in TOPICS if x["code"] != "CHAT"]
                    if roll < high_p + med_p:
                        pool = [x for x in pool if x["code"] not in ("KNOW", "CHAT")]
                    topic = rnd.choice(pool)
                    user_text = rnd.choice(topic["user"])
                    intent = topic["intent"]
                    if topic["code"] == "CHAT":
                        risk = "LOW"
                    elif roll < high_p + med_p:
                        risk = "MEDIUM"
                    else:
                        risk = "LOW"
                    reply = make_reply(rnd, topic)
                    keywords = None

                if title is None:
                    title = user_text[:20]

                conv_messages.append({
                    "uid": msg_id, "role": "user", "content": user_text,
                    "intent": None, "risk": None, "tokens": 0, "time": t,
                })
                msg_id += 1

                # 学生那条消息的 id 用于预警定位
                user_msg_id = conv_messages[-1]["uid"]

                conv_messages.append({
                    "uid": msg_id, "role": "assistant", "content": reply,
                    "intent": intent, "risk": risk,
                    "tokens": rnd.randint(120, 460) if intent != "CHITCHAT" else rnd.randint(20, 60),
                    "time": t + timedelta(seconds=rnd.randint(4, 25)),
                })
                msg_id += 1

                if risk == "HIGH":
                    conv_max_risk = "HIGH"
                    if conv_high_alert_msg is None:
                        conv_high_alert_msg = (user_msg_id, keywords or "高危表达")
                elif risk == "MEDIUM" and conv_max_risk == "LOW":
                    conv_max_risk = "MEDIUM"

                # 中/高风险生成工单
                if risk in ("MEDIUM", "HIGH"):
                    # 越早的工单越可能已经处理完，避免演示数据里堆着几个月前的积压件；
                    # 近一周内的工单大部分仍是待处理状态，这样「待处理」才像真实的工作量。
                    # 超过 45 天一律视为已处理，否则会出现「积压 3 个月」这种不合常理的记录。
                    if start_day > 45:
                        handled_p = 1.0
                    elif start_day > 30:
                        handled_p = 0.90
                    elif start_day > 7:
                        handled_p = 0.78
                    else:
                        handled_p = 0.22
                    handled = rnd.random() < handled_p
                    create_t = conv_messages[-1]["time"] + timedelta(seconds=2)
                    handle_t = None
                    handler = None
                    remark = None
                    status = "PENDING"
                    if handled:
                        handle_t, _ = _handle_time(rnd, create_t, risk == "HIGH")
                        if handle_t > now:
                            handled = False
                            handle_t = None
                        else:
                            handler = rnd.choice(counselor_ids)
                            remark = rnd.choice(HANDLE_REMARKS)
                            status = rnd.choices(["HANDLED", "CLOSED"], weights=[80, 20])[0]
                    alert_rows.append({
                        "id": alert_id, "source": "CHAT", "conv": conv_id, "msg": user_msg_id,
                        "assess": None, "uid": stu["id"], "risk": risk,
                        "keywords": keywords or ("压力,情绪低落" if risk == "MEDIUM" else "高危表达"),
                        "content": user_text, "suggest": None, "status": status,
                        "handler": handler, "remark": remark, "create": create_t, "handle": handle_t,
                    })
                    alert_id += 1

            conv_status = 0 if rnd.random() < 0.55 else 1
            last_time = conv_messages[-1]["time"]
            conv_rows.append({
                "id": conv_id, "uid": stu["id"], "title": title, "risk": conv_max_risk,
                "turns": turn_n, "status": conv_status, "create": conv_time, "update": last_time,
            })
            for m in conv_messages:
                msg_rows.append({"id": m["uid"], "conv": conv_id, "uid": stu["id"], **m})

            # 已结束的会话生成报告
            if conv_status == 0 and rnd.random() < 0.8:
                base = {"LOW": rnd.randint(62, 86), "MEDIUM": rnd.randint(40, 60),
                        "HIGH": rnd.randint(8, 32)}[conv_max_risk]
                summary_subject = {
                    "LOW": "学业节奏与日常情绪",
                    "MEDIUM": "学业压力与睡眠困扰",
                    "HIGH": "自伤念头与持续性情绪低落",
                }[conv_max_risk]
                report_rows.append({
                    "id": report_id, "conv": conv_id, "uid": stu["id"],
                    "summary": rnd.choice(REPORT_SUMMARY[conv_max_risk]).format(s=summary_subject),
                    "score": base, "risk": conv_max_risk,
                    "suggest": REPORT_SUGGEST[conv_max_risk],
                    "create": last_time + timedelta(minutes=rnd.randint(1, 30)),
                })
                report_id += 1

            conv_id += 1

    add("-- ---------------- 会话 ----------------")
    add("INSERT INTO `conversation` (`id`, `user_id`, `title`, `risk_level`, `turn_count`, `status`, `create_time`, `update_time`) VALUES")
    add(",\n".join(
        "  (%d, %d, %s, %s, %d, %d, %s, %s)" % (
            c["id"], c["uid"], sql_str(c["title"]), sql_str(c["risk"]), c["turns"], c["status"],
            sql_str(c["create"].strftime("%Y-%m-%d %H:%M:%S")),
            sql_str(c["update"].strftime("%Y-%m-%d %H:%M:%S")))
        for c in conv_rows) + ";")
    add("")

    add("-- ---------------- 消息 ----------------")
    CHUNK = 200
    for i in range(0, len(msg_rows), CHUNK):
        add("INSERT INTO `message` (`id`, `conversation_id`, `user_id`, `role`, `content`, `intent`, `risk_level`, `tokens`, `create_time`) VALUES")
        add(",\n".join(
            "  (%d, %d, %d, %s, %s, %s, %s, %d, %s)" % (
                m["id"], m["conv"], m["uid"], sql_str(m["role"]), sql_str(m["content"]),
                sql_str_or_null(m["intent"]), sql_str_or_null(m["risk"]), m["tokens"],
                sql_str(m["time"].strftime("%Y-%m-%d %H:%M:%S")))
            for m in msg_rows[i:i + CHUNK]) + ";")
        add("")

    # ---------- 量表测评 ----------
    assess_rows = []
    for stu in students:
        if rnd.random() < 0.42:
            continue
        n = rnd.choices([1, 2, 3], weights=[52, 33, 15])[0]
        for _ in range(n):
            cfg = rnd.choice(ASSESS_TYPES)
            # 让总分分布偏向中低区间，更接近真实筛查
            bias = rnd.choices([0, 1, 2, 3], weights=[40, 30, 20, 10])[0]
            answers = [min(3, rnd.choices([0, 1, 2, 3], weights=[45, 28, 18, 9])[0] + (1 if bias >= 2 and rnd.random() < 0.4 else 0))
                       for _ in range(cfg["count"])]
            score = sum(answers)
            severity, label = assess_level(cfg, score)
            risk = assess_risk(cfg, score, answers)
            high_items = None
            if cfg["critical_item"] is not None and answers[cfg["critical_item"]] > 0:
                high_items = str(cfg["critical_item"] + 1)
            if risk == "HIGH" and not high_items:
                high_items = str(rnd.randint(2, cfg["count"]))

            at = now - timedelta(days=rnd.randint(0, DAYS_SPAN - 1),
                                 hours=rnd.randint(0, 23), minutes=rnd.randint(0, 59))
            if at > now:
                at = now - timedelta(hours=rnd.randint(1, 40))
            assess_rows.append({
                "id": len(assess_rows) + 1, "uid": stu["id"], "code": cfg["code"],
                "name": cfg["name"], "score": score, "severity": severity, "label": label,
                "risk": risk, "answers": ",".join(str(a) for a in answers),
                "items": high_items, "time": at, "max": cfg["max_score"],
            })

    assess_rows.sort(key=lambda x: x["time"])
    for i, a in enumerate(assess_rows):
        a["id"] = i + 1

    add("-- ---------------- 心理测评记录 ----------------")
    add("INSERT INTO `assessment_record` (`id`, `user_id`, `scale_code`, `scale_name`, `total_score`, `severity`, `severity_label`, `risk_level`, `answers`, `high_risk_items`, `create_time`) VALUES")
    add(",\n".join(
        "  (%d, %d, %s, %s, %d, %s, %s, %s, %s, %s, %s)" % (
            a["id"], a["uid"], sql_str(a["code"]), sql_str(a["name"]), a["score"],
            sql_str(a["severity"]), sql_str(a["label"]), sql_str(a["risk"]),
            sql_str(a["answers"]), sql_str_or_null(a["items"]),
            sql_str(a["time"].strftime("%Y-%m-%d %H:%M:%S")))
        for a in assess_rows) + ";")
    add("")

    # ---------- 量表预警工单 ----------
    for a in assess_rows:
        if a["risk"] == "LOW":
            continue
        if a["risk"] == "MEDIUM" and rnd.random() > 0.5:
            continue
        age_days = (now - a["time"]).days
        if age_days > 45:
            handled = True
        elif age_days > 7:
            handled = rnd.random() < (0.85 if a["risk"] == "HIGH" else 0.72)
        else:
            handled = rnd.random() < (0.35 if a["risk"] == "HIGH" else 0.15)
        create_t = a["time"] + timedelta(seconds=1)
        handle_t = None
        handler = None
        remark = None
        status = "PENDING"
        if handled:
            handle_t, _ = _handle_time(rnd, create_t, a["risk"] == "HIGH")
            if handle_t > now:
                handle_t = None
            else:
                handler = rnd.choice(counselor_ids)
                remark = rnd.choice(HANDLE_REMARKS)
                status = "HANDLED"
        extra = "，第 %s 题涉及自伤念头" % a["items"] if a["items"] else ""
        alert_rows.append({
            "id": alert_id, "source": "ASSESSMENT", "conv": None, "msg": None,
            "assess": a["id"], "uid": a["uid"], "risk": a["risk"],
            "keywords": ("第 %s 题" % a["items"]) if a["items"] else a["label"],
            "content": ASSESS_ALERT_CONTENT.format(name=a["name"], label=a["label"],
                                                   score=a["score"], max=a["max"], extra=extra),
            "suggest": REPORT_SUGGEST[a["risk"]], "status": status,
            "handler": handler, "remark": remark, "create": create_t, "handle": handle_t,
        })
        alert_id += 1

    alert_rows.sort(key=lambda x: x["create"])
    for i, al in enumerate(alert_rows):
        al["id"] = i + 1

    add("-- ---------------- 风险工单 ----------------")
    CHUNK = 120
    for i in range(0, len(alert_rows), CHUNK):
        add("INSERT INTO `risk_alert` (`id`, `source`, `conversation_id`, `message_id`, `assessment_record_id`, `user_id`, `risk_level`, `keywords`, `content`, `ai_suggestion`, `status`, `handler_id`, `handle_remark`, `create_time`, `handle_time`) VALUES")
        add(",\n".join(
            "  (%d, %s, %s, %s, %s, %d, %s, %s, %s, %s, %s, %s, %s, %s, %s)" % (
                al["id"], sql_str(al["source"]), str(al["conv"]) if al["conv"] else "NULL",
                str(al["msg"]) if al["msg"] else "NULL",
                str(al["assess"]) if al["assess"] else "NULL",
                al["uid"], sql_str(al["risk"]), sql_str_or_null(al["keywords"]),
                sql_str(al["content"]),
                sql_str(al["suggest"] or _default_suggest(al["risk"])),
                sql_str(al["status"]),
                str(al["handler"]) if al["handler"] else "NULL",
                sql_str_or_null(al["remark"]),
                sql_str(al["create"].strftime("%Y-%m-%d %H:%M:%S")),
                sql_str(al["handle"].strftime("%Y-%m-%d %H:%M:%S")) if al["handle"] else "NULL")
            for al in alert_rows[i:i + CHUNK]) + ";")
        add("")

    add("-- ---------------- 咨询报告 ----------------")
    CHUNK = 150
    for i in range(0, len(report_rows), CHUNK):
        add("INSERT INTO `consult_report` (`id`, `conversation_id`, `user_id`, `summary`, `emotion_score`, `risk_level`, `suggestion`, `create_time`) VALUES")
        add(",\n".join(
            "  (%d, %d, %d, %s, %d, %s, %s, %s)" % (
                r["id"], r["conv"], r["uid"], sql_str(r["summary"]), r["score"], sql_str(r["risk"]),
                sql_str(r["suggest"]), sql_str(r["create"].strftime("%Y-%m-%d %H:%M:%S")))
            for r in report_rows[i:i + CHUNK]) + ";")
        add("")

    add("ALTER TABLE `user` AUTO_INCREMENT = %d;" % (uid + 1))
    add("ALTER TABLE `risk_alert` AUTO_INCREMENT = %d;" % (alert_id + 1))
    add("ALTER TABLE `consult_report` AUTO_INCREMENT = %d;" % (report_id + 1))
    add("ALTER TABLE `conversation` AUTO_INCREMENT = %d;" % (conv_id + 1))
    add("ALTER TABLE `message` AUTO_INCREMENT = %d;" % (msg_id + 1))
    add("ALTER TABLE `assessment_record` AUTO_INCREMENT = %d;" % (len(assess_rows) + 1))
    add("")
    add("SELECT")
    add("  (SELECT COUNT(*) FROM `user`)               AS users,")
    add("  (SELECT COUNT(*) FROM `conversation`)       AS conversations,")
    add("  (SELECT COUNT(*) FROM `message`)            AS messages,")
    add("  (SELECT COUNT(*) FROM `risk_alert`)         AS alerts,")
    add("  (SELECT COUNT(*) FROM `assessment_record`)  AS assessments,")
    add("  (SELECT COUNT(*) FROM `consult_report`)     AS reports;")

    out = os.path.normpath(OUT_PATH)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    print("written: %s" % out)
    print("students=%d conversations=%d messages=%d alerts=%d assessments=%d reports=%d"
          % (len(students), len(conv_rows), len(msg_rows), len(alert_rows),
             len(assess_rows), len(report_rows)))


def _default_suggest(risk):
    return REPORT_SUGGEST.get(risk, REPORT_SUGGEST["MEDIUM"])


def _handle_time(rnd, create_t, is_high):
    """处置时长：集中在数小时内，少量跨越一两天；高危件响应明显更快。"""
    if is_high:
        weights = [18, 26, 24, 16, 10, 5, 1]
    else:
        weights = [8, 16, 20, 20, 17, 12, 7]
    minutes = rnd.choices([20, 60, 150, 360, 720, 1440, 2880], weights=weights)[0]
    return create_t + timedelta(minutes=minutes), minutes


if __name__ == "__main__":
    main()
