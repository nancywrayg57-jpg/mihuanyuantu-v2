"""脱敏引擎的红队语料测试。

安全能力最容易出现的问题是"测试全绿但一个都挡不住"——本能力的第一版就是：
正则用了 `\b`，在中文语料上一个手机号都没挡住，而当时的测试是拿英文写的，全绿。

所以这里的断言方式是**反向**的：给一段输入，声明哪些字符串**绝不允许**出现在
输出里。加新的绕过写法时往 `samples/redteam.json` 里加，不要只加正则。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.redaction import (
    Action,
    EntityKind,
    FieldRule,
    KnownValue,
    RedactionBlocked,
    RedactionPolicy,
    Redactor,
    enforce,
    scan,
)

CORPUS = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "app/core/redaction/samples/redteam.json"
    ).read_text(encoding="utf-8")
)

#: 语料用的策略：五个自由文本字段都 pass（模型需要看内容），靠 L2/L3 清里面的实体。
CORPUS_POLICY = RedactionPolicy(
    version=1,
    field_rules={
        key: FieldRule(action=Action.PASS)
        for key in ("done", "results", "blockers", "resources", "plan")
    },
)


def _known(raw: list[dict] | None) -> list[KnownValue]:
    return [
        KnownValue(kind=EntityKind(item["kind"]), value=item["value"])
        for item in (raw or [])
    ]


@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda c: c["id"])
def test_redteam_corpus(case: dict) -> None:
    redactor = Redactor(CORPUS_POLICY)
    result = redactor.redact_document(
        fields=case["fields"], known_values=_known(case.get("known_values"))
    )
    joined = "\n".join(result.fields.values())

    for forbidden in case.get("must_not_contain", []):
        assert forbidden not in joined, (
            f"[{case['id']}] 敏感值泄露到出云内容里：{forbidden!r}\n"
            f"理由：{case.get('why', '')}\n实际输出：{joined!r}"
        )
    for required in case.get("must_contain", []):
        assert required in joined, (
            f"[{case['id']}] 业务证据被误伤了：{required!r} 不见了\n实际输出：{joined!r}"
        )


@pytest.mark.parametrize("case", CORPUS["guard_cases"], ids=lambda c: c["id"])
def test_outbound_guard(case: dict) -> None:
    """守卫必须独立于前面几层生效——这里**故意不经过 Redactor**，直接喂原文。"""
    if case["expect_blocked"]:
        with pytest.raises(RedactionBlocked) as captured:
            enforce(case["fields"], CORPUS_POLICY)
        # 异常信息会一路传到前端：只能有类别，不能回显原值
        message = str(captured.value)
        for raw in case["fields"].values():
            assert raw not in message, f"守卫的报错里回显了原值：{message}"
    else:
        assert enforce(case["fields"], CORPUS_POLICY) == case["fields"]


def test_allowlist_blocks_undeclared_fields() -> None:
    """没在策略里声明的字段**默认出不去**。这一条就是 allowlist 本身。"""
    policy = RedactionPolicy(version=1, field_rules={"done": FieldRule(action=Action.PASS)})
    result = Redactor(policy).redact_document(
        fields={"done": "正常内容", "secret_note": "不该出云的内容"}
    )
    assert "secret_note" not in result.fields
    assert "secret_note" in result.blocked_fields
    assert "不该出云的内容" not in "\n".join(result.fields.values())


def test_pseudonyms_preserve_coreference() -> None:
    """假名化而不是抹除：模型要能分清两个客户，否则指代关系整个塌掉。"""
    policy = RedactionPolicy(version=1, field_rules={"done": FieldRule(action=Action.PASS)})
    redactor = Redactor(policy)
    result = redactor.redact_document(
        fields={"done": "拜访了阿尔法科技和贝塔实业，阿尔法科技签了单"},
        known_values=[
            KnownValue(kind=EntityKind.ORG, value="阿尔法科技"),
            KnownValue(kind=EntityKind.ORG, value="贝塔实业"),
        ],
    )
    text = result.fields["done"]
    tokens = {ph.original: token for token, ph in result.mapping.items()}
    alpha, beta = tokens["阿尔法科技"], tokens["贝塔实业"]
    assert alpha in text and beta in text and alpha != beta
    # 同一家公司出现两次必须是同一个代号，否则模型追不住"签单的是哪一家"
    assert text.count(alpha) == 2


def test_restore_round_trip() -> None:
    """返回路径必须还原，否则人看到的证据引用和他眼里的原文对不上。"""
    policy = RedactionPolicy(version=1, field_rules={"done": FieldRule(action=Action.PASS)})
    redactor = Redactor(policy)
    redactor.redact_document(
        fields={"done": "张伟说13800138000可以直接打"},
        known_values=[
            KnownValue(kind=EntityKind.PERSON, value="张伟"),
            KnownValue(kind=EntityKind.PHONE, value="13800138000"),
        ],
    )
    tokens = {ph.original: token for token, ph in redactor.mapping.items()}
    person, phone = tokens["张伟"], tokens["13800138000"]
    model_output = {
        "evidence": f"{person}留了{phone}",
        # 模型可能把 〔…〕 写成 【…】，容错的是括号不是身份
        "quote": f"{person.replace('〔', '【').replace('〕', '】')}说",
    }
    restored = redactor.restore(model_output)
    assert restored["evidence"] == "张伟留了13800138000"
    assert restored["quote"] == "张伟说"


def test_findings_never_carry_raw_values() -> None:
    """审计只记类别和数量。映射表不落库、不进日志、不进审计。"""
    policy = RedactionPolicy(version=1, field_rules={"done": FieldRule(action=Action.PASS)})
    redactor = Redactor(policy)
    result = redactor.redact_document(fields={"done": "手机13800138000"})
    summary = json.dumps(result.audit_summary(), ensure_ascii=False)
    assert "13800138000" not in summary
    assert result.findings and all(not hasattr(f, "value") for f in result.findings)


def test_always_blocked_kinds_survive_policy_misconfiguration() -> None:
    """身份证和银行卡没有任何"模型需要看到"的理由——策略把探测器关光也要挡住。"""
    policy = RedactionPolicy(
        version=1,
        field_rules={"done": FieldRule(action=Action.PASS)},
        detectors=frozenset(),  # 探测器全关
    )
    result = Redactor(policy).redact_document(fields={"done": "身份证110101199001011234"})
    assert "110101199001011234" not in result.fields["done"]


def test_scanner_actually_catches_a_real_violation() -> None:
    """NEW_MODULE.md §8 的硬规则：新增的扫描器必须注入一次真实违规并确认变红。

    没做过这一步的安全测试不能算数——第一版的测试就是全绿但抓不到任何东西。
    """
    assert scan({"done": "13800138000"}), "守卫连裸手机号都抓不到"
    assert not scan({"done": "签约2家，回款18万"}), "守卫误伤了正常业务数字"


# ---------------------------------------------------------------------------
# 候选实体识别（点选确认的第一步）
# ---------------------------------------------------------------------------


def test_candidates_are_silent_when_there_is_nothing_to_confirm() -> None:
    """没东西要确认时必须返回空——否则每写一句话都弹一堆东西，用户就学会无视它了。"""
    from app.core.redaction import find_candidates

    assert find_candidates({"done": "今天签约2家，回款18万，完成率85%，明天回访"}) == []


def test_candidates_trim_leading_verbs_and_particles() -> None:
    """中文里名字前面常粘着时间词和动词，正则往左是贪心的。

    框得准不准只影响体验、不影响安全，但框成"上午拜访华为技术有限公司"
    会让用户觉得这东西不靠谱，进而不用它——那安全性就真的受影响了。
    """
    from app.core.redaction import find_candidates

    found = {c.text for c in find_candidates(
        {"done": "上午拜访华为技术有限公司，张总说要推进；下午跟贝塔科技的李经理谈了"}
    )}
    assert "华为技术有限公司" in found
    assert "贝塔科技" in found
    assert "张总" in found and "李经理" in found
    assert not any(t.startswith(("上午", "下午", "的")) for t in found), found


def test_candidates_skip_generic_org_words() -> None:
    """"对方公司""我们公司"是泛指，弹给用户确认只会制造噪声。"""
    from app.core.redaction import find_candidates

    found = {c.text for c in find_candidates({"done": "对方公司还在评估，我们公司这边已经准备好"})}
    assert not found & {"对方公司", "我们公司", "公司"}


def test_high_confidence_candidates_need_no_confirmation() -> None:
    """手机号本来就会被脱敏，不该要求用户为它表态——只是让他看见系统注意到了。"""
    from app.core.redaction import find_candidates

    phone = [c for c in find_candidates({"done": "电话13800138000"}) if c.kind == EntityKind.PHONE]
    assert phone and phone[0].confidence == "high"
    assert phone[0].needs_confirmation is False


def test_confirmed_entity_upgrades_guess_to_knowledge() -> None:
    """确认之后，L2 按真值精确替换——这就是点选确认的全部意义。

    没确认时，"阿尔法" 这个简称 L3 猜不出来（它不像手机号有格式）；
    确认了全称之后，简称也能被 L2 的机构名变体覆盖掉。
    """
    policy = RedactionPolicy(version=1, field_rules={"done": FieldRule(action=Action.PASS)})
    text = {"done": "阿尔法智能科技有限公司签了单，阿尔法那边很积极"}

    without = Redactor(policy).redact_document(fields=text)
    assert "阿尔法" in without.fields["done"], "没确认时确实猜不出来（这正是要解决的问题）"

    with_confirmation = Redactor(policy).redact_document(
        fields=text,
        known_values=[KnownValue(kind=EntityKind.ORG, value="阿尔法智能科技有限公司")],
    )
    assert "阿尔法" not in with_confirmation.fields["done"]
    assert next(iter(with_confirmation.mapping)) in with_confirmation.fields["done"]


# ---------------------------------------------------------------------------
# 代号本身的正确性
# ---------------------------------------------------------------------------


def test_user_written_placeholder_lookalike_is_not_corrupted() -> None:
    """用户自己在正文里写了代号形状的内容，不能被还原改掉。

    没有 nonce 的时候，"备注〔客户1〕是内部编号" 会被还原成
    "备注华为技术是内部编号"——用户的日报里出现了他没写过的内容。
    这是**数据损坏**，而且悄无声息：他下次翻历史才会发现，那时已经说不清是谁改的。
    """
    policy = RedactionPolicy(version=1, field_rules={"done": FieldRule(action=Action.PASS)})
    redactor = Redactor(policy)
    result = redactor.redact_document(
        fields={"done": "备注〔客户1〕是内部编号，另外拜访了华为技术"},
        known_values=[KnownValue(kind=EntityKind.ORG, value="华为技术")],
    )
    restored = redactor.restore(result.fields["done"])
    assert "备注〔客户1〕是内部编号" in restored, restored
    assert restored.count("华为技术") == 1, restored


def test_restore_does_not_touch_ordinary_bracketed_text() -> None:
    """容错还原只容忍括号写法，不容忍身份不明。

    `【客户1】的报价单` 是用户写的普通文本，nonce 对不上就不许动它。
    """
    policy = RedactionPolicy(version=1, field_rules={"done": FieldRule(action=Action.PASS)})
    redactor = Redactor(policy)
    redactor.redact_document(
        fields={"done": "拜访华为技术"},
        known_values=[KnownValue(kind=EntityKind.ORG, value="华为技术")],
    )
    for text in ("【客户1】的报价单", "[客户2]尚未联系", "【重要】明天开会", "(联系人3) 待确认"):
        assert redactor.restore(text) == text, text


def test_restore_tolerates_model_reformatting_the_brackets() -> None:
    """模型可能把 〔…〕 写成 【…】。容错的是括号，nonce 仍然要对上。"""
    policy = RedactionPolicy(version=1, field_rules={"done": FieldRule(action=Action.PASS)})
    redactor = Redactor(policy)
    redactor.redact_document(
        fields={"done": "拜访华为技术"},
        known_values=[KnownValue(kind=EntityKind.ORG, value="华为技术")],
    )
    token = next(iter(redactor.mapping))
    assert redactor.restore(token.replace("〔", "【").replace("〕", "】")) == "华为技术"


def test_numbering_does_not_carry_across_documents() -> None:
    """代号编号每份记录从 1 开始。

    跨记录复用会让"客户7"在多份报告之间可关联——那等于自己削弱了去标识化强度。
    """
    policy = RedactionPolicy(version=1, field_rules={"done": FieldRule(action=Action.PASS)})
    tokens = []
    for name in ("甲公司", "乙公司"):
        redactor = Redactor(policy)
        redactor.redact_document(
            fields={"done": name}, known_values=[KnownValue(kind=EntityKind.ORG, value=name)]
        )
        tokens.append(next(iter(redactor.mapping)))
    assert all("客户1" in token for token in tokens)
    # nonce 不同，所以两份记录的代号不会互相匹配
    assert tokens[0] != tokens[1]


# ---------------------------------------------------------------------------
# 策略配错时必须保守
# ---------------------------------------------------------------------------


def test_misconfigured_policy_fails_closed() -> None:
    """配错了却看起来在保护，比不保护更危险。

    `pseudonymize` 需要知道类别才能执行。kind 写错或缺失时，如果落回"原样发送"，
    管理员会以为这个字段被保护着——直到某天有人去看请求日志才发现一直在裸发。
    """
    policy = RedactionPolicy.from_json(
        {
            "fieldRules": {
                "secret": {"action": "pseudonymize"},                 # 缺 kind
                "other": {"action": "pseudonymize", "kind": "什么鬼"},   # kind 写错
                "third": {"action": "pas"},                           # action 拼错
                "fourth": "不是个对象",                                  # 类型都不对
            }
        }
    )
    for key in ("secret", "other", "third", "fourth"):
        assert policy.rule_for(key).action == Action.BLOCK, key

    result = Redactor(policy).redact_document(
        fields={"secret": "13800138000", "other": "张伟", "third": "x", "fourth": "y"}
    )
    assert result.fields == {}
    assert sorted(result.blocked_fields) == ["fourth", "other", "secret", "third"]


def test_missing_detectors_key_uses_defaults_not_empty() -> None:
    """策略里没写 detectors ≠ 一个探测器都不要。

    "没写"通常意味着写策略的人没想到这一项，而不是他决定全部关掉。
    按"全关"处理会让一份看似正常的策略静默丢掉全部兜底。
    显式给空列表才是"我确实要全关"。
    """
    implicit = RedactionPolicy.from_json({"fieldRules": {"done": {"action": "pass"}}})
    assert EntityKind.PHONE in implicit.detectors

    explicit = RedactionPolicy.from_json(
        {"fieldRules": {"done": {"action": "pass"}}, "detectors": []}
    )
    assert explicit.detectors == frozenset()
    # 但身份证/银行卡永远挡——策略关不掉它们
    result = Redactor(explicit).redact_document(fields={"done": "身份证110105194912310021"})
    assert "110105194912310021" not in result.fields["done"]


def test_guard_is_independent_of_the_earlier_layers() -> None:
    """守卫必须能独立拦住——即使前面几层全部失效。

    实测过的失败模式：守卫整段贪心取数字，`联系13800138000 2次` 被合并成 12 位，
    "既不是手机也不是卡号"于是整段忽略。前层挡住了所以没出事，
    但那意味着"独立兜底"只是名义上的。
    """
    for text in (
        "13800138000",
        "联系13800138000 2次",
        "联系13800138000 2026年",
        "一三八〇〇一三八〇〇〇",
        "138.0013.8000",
        "138（0013）8000",
    ):
        assert scan({"done": text}), f"守卫漏了：{text!r}"

    for text in ("签约2家，跟进12个客户，完成率85%，回款18万", "2026年第3季度", "拜访了5家"):
        assert not scan({"done": text}), f"守卫误伤了正常业务数字：{text!r}"


def test_hash_cannot_be_used_to_smuggle_always_blocked_kinds() -> None:
    """身份证、银行卡不能用 HASH "代替"阻断。

    取值空间可枚举，无盐哈希还跨记录稳定可关联——那不是阻断，
    是换了个形式的标识符。`ALWAYS_BLOCKED` 声称"策略怎么配都挡"，
    HASH 分支必须遵守这句话，否则这个常量就是一句空话。
    """
    policy = RedactionPolicy(
        version=1,
        field_rules={"identity": FieldRule(action=Action.HASH, kind=EntityKind.ID_CARD)},
    )
    result = Redactor(policy).redact_document(fields={"identity": "110105194912310021"})
    assert result.fields == {}
    assert "identity" in result.blocked_fields


def test_hash_is_salted_so_it_is_not_globally_enumerable() -> None:
    """令牌化要跨记录稳定（这是它的用途），但不能是裸 sha256。"""
    import hashlib

    policy = RedactionPolicy(
        version=7, field_rules={"device": FieldRule(action=Action.HASH, kind=EntityKind.SERIAL)}
    )
    token = Redactor(policy).redact_document(fields={"device": "SN-0001"}).fields["device"]
    assert hashlib.sha256(b"SN-0001").hexdigest()[:16] not in token
    # 同一策略版本下稳定——否则"是不是同一台设备"就判断不了
    again = Redactor(policy).redact_document(fields={"device": "SN-0001"}).fields["device"]
    assert token == again


def test_nonce_is_wide_enough_to_avoid_frequent_cross_record_repeats() -> None:
    """nonce 太短会让相同 token 跨记录反复出现。

    重复本身不泄露什么（A 记录的"客户1"和 B 记录的"客户1"是不同实体），
    但那是白送给外部服务的关联信号。4 位十六进制实测 5000 份记录重复 167 次。
    """
    policy = RedactionPolicy(version=1, field_rules={"done": FieldRule(action=Action.PASS)})
    nonces = {Redactor(policy).nonce for _ in range(2000)}
    assert len(nonces) > 1990, f"nonce 空间太小，2000 次生成只得到 {len(nonces)} 个不同值"


# ---------------------------------------------------------------------------
# 开关：AI 和脱敏都是可选项
# ---------------------------------------------------------------------------


