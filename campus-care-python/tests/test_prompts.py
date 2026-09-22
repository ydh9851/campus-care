"""prompt 外置与版本管理的测试。

这些断言看起来简单，但正是它们保证了「改 prompt 不会悄悄改坏链路」：
文件缺失会立刻失败，版本号不稳定会让线上回溯失效。
"""
from __future__ import annotations

from app.prompts import KNOWN_PROMPTS, fill, load_json_prompt, load_prompt, prompt_version, prompt_versions


def test_all_known_prompts_loadable():
    for name in KNOWN_PROMPTS:
        text = load_prompt(name) if name != "reply_style" else None
        if text is None:
            data = load_json_prompt(name)
            assert data, f"{name} 为空"
        else:
            assert text.strip(), f"{name} 为空"


def test_prompt_version_is_stable_and_short():
    v1 = prompt_version("intent")
    v2 = prompt_version("intent")
    assert v1 == v2
    assert len(v1) == 8


def test_prompt_versions_covers_all():
    versions = prompt_versions()
    assert set(versions) == set(KNOWN_PROMPTS)
    assert all(len(v) == 8 for v in versions.values())


def test_fill_replaces_placeholder():
    assert fill("学生发言：{message}", message="我好累") == "学生发言：我好累"


def test_reply_style_has_all_intents():
    styles = load_json_prompt("reply_style")
    for intent in ("PSYCH_EMOTION", "KNOWLEDGE_QUERY", "RISK_ALERT", "CHITCHAT"):
        assert intent in styles
