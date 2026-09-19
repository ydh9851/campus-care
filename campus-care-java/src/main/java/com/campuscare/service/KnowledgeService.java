package com.campuscare.service;

import com.campuscare.client.PythonAgentClient;
import com.campuscare.dto.KnowledgeCategory;
import com.campuscare.dto.KnowledgeItem;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 心理科普内容服务。
 *
 * 语料（105 条 FAQ）在 Python 侧，Java 只做代理，三个取舍：
 *
 * 1. **一次性取回全部条目并缓存**，而不是按关键词逐次穿透到 Python。
 *    浏览场景下用户会反复换分类、改关键词，每次都往返一次网络毫无意义；
 *    总量只有百来条纯文本，全量传输的成本远低于一次次往返。
 *
 * 2. **过滤放在本地做**。分类和关键词都是内存里的字符串比较，
 *    交给 Python 反而要多传参数、多一次往返。
 *
 * 3. **缓存 5 分钟**。改了 FAQ 不必重启 Java，也不会每个请求都打 Python。
 *    附带的好处：Python 临时不可用时，科普页仍能凭旧缓存打开 ——
 *    这是静态语料，用几分钟前的数据远好过整页报错。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeService {

    private static final long CACHE_TTL_MS = 5 * 60 * 1000L;

    private final PythonAgentClient pythonAgentClient;

    private volatile List<KnowledgeItem> cache;
    private volatile long cachedAt;

    /** 按分类与关键词过滤，两者都为空时返回全部 */
    public List<KnowledgeItem> list(String category, String keyword) {
        String cat = category == null ? "" : category.trim();
        String kw = keyword == null ? "" : keyword.trim().toLowerCase();

        List<KnowledgeItem> hit = new ArrayList<>();
        for (KnowledgeItem item : allItems()) {
            // 前端「全部」标签传的就是「全部」两个字，这里一并当作不过滤
            if (!cat.isEmpty() && !"全部".equals(cat) && !cat.equals(item.getCategory())) {
                continue;
            }
            if (!kw.isEmpty() && !matches(item, kw)) {
                continue;
            }
            hit.add(item);
        }
        return hit;
    }

    /** 分类及条数，按条数倒序（条数多的分类更可能是用户想先看的） */
    public List<KnowledgeCategory> categories() {
        Map<String, Integer> counter = new LinkedHashMap<>();
        for (KnowledgeItem item : allItems()) {
            String name = item.getCategory() == null || item.getCategory().isBlank()
                    ? "通用"
                    : item.getCategory();
            counter.merge(name, 1, Integer::sum);
        }
        List<KnowledgeCategory> list = new ArrayList<>();
        counter.forEach((name, count) -> list.add(new KnowledgeCategory(name, count)));
        list.sort(Comparator.comparingInt(KnowledgeCategory::getCount).reversed());
        return list;
    }

    /** 标题 / 正文 / 出处任一命中即可 */
    private boolean matches(KnowledgeItem item, String kw) {
        return lower(item.getTitle()).contains(kw)
                || lower(item.getContent()).contains(kw)
                || lower(item.getSource()).contains(kw);
    }

    private String lower(String s) {
        return s == null ? "" : s.toLowerCase();
    }

    private List<KnowledgeItem> allItems() {
        long now = System.currentTimeMillis();
        List<KnowledgeItem> local = cache;

        if (local != null && now - cachedAt < CACHE_TTL_MS) {
            return local;
        }

        try {
            List<KnowledgeItem> fresh = pythonAgentClient.kbItems();
            cache = fresh;
            cachedAt = now;
            log.info("知识库缓存已刷新，共 {} 条", fresh.size());
            return fresh;
        } catch (RuntimeException e) {
            if (local == null) {
                throw e;
            }
            log.warn("刷新知识库失败，继续使用 {} 分钟前的缓存：{}", (now - cachedAt) / 60000, e.getMessage());
            // 把时间戳往后推，避免每个请求都去撞一次已经失败的下游
            cachedAt = now;
            return local;
        }
    }
}
