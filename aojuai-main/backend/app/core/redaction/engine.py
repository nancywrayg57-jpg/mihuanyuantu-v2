"""脱敏引擎：L1 字段策略 + L2 已知值回扫 + L3 模式兜底，以及返回路径的还原。

纯函数式：输入文本与策略，输出脱敏结果与映射表，不碰数据库、不发网络请求。
这样才能被红队语料直接驱动（见 `samples/redteam.json`）。

**一个实现决定值得说明**：匹配和替换都在 NFKC 规范化后的副本上进行。
全角数字 `１３８００１３８０００` 不折成半角就匹配不上，而"在规范化文本上匹配、
回到原文替换"需要维护偏移映射，NFKC 又不保证长度不变（`㈱`→`(株)`），
偏移映射本身就是 bug 温床。所以直接把规范化后的文本当作出云内容——
**库里的原文一个字节都不动**，人看到的永远是原文，只有模型看到规范化+假名化的版本。

映射表随请求生命周期存活：不落库、不进日志、不进审计。审计里只记
"命中了 3 处手机号"，不记是哪三处、更不记值。
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from typing import Any

from .detectors import (
    AMOUNT_PATTERN,
    DETECTORS,
    PHONE_TAIL_PATTERN,
    SEPARATORS,
    amount_to_wan,
    normalize_for_match,
)
from .policy import (
    ALWAYS_BLOCKED,
    ENTITY_LABELS,
    Action,
    EntityKind,
    RedactionPolicy,
    bucket_amount,
)

#: 假名格式 `〔客户1·a7f3〕`。U+3014/U+3015 在中文商务文本里几乎不出现，
#: 视觉上一眼可辨，模型也不会把它当错别字"顺手修正"。
_OPEN, _CLOSE = "〔", "〕"

#: 末尾那段随机 nonce 不是装饰，是**正确性的必要条件**。
#:
#: 没有它的时候，用户自己在正文里写一句"备注〔客户1〕是内部编号"，就会和生成的
#: 假名撞上：还原时那句话被改成"备注华为技术是内部编号"——用户的日报里出现了
#: 他没写过的内容。这是数据损坏，而且悄无声息。
#: 同样地，容错还原会把用户写的 `【客户1】的报价单` 也一起改掉。
#:
#: nonce 每个 Redactor 实例（= 每次请求）重新生成，用户写不出来，于是
#: "生成的假名"和"用户碰巧写的相似文本"从此可以区分。
#:
#: 长度取 8（32 位）而不是 4：4 位十六进制只有 65536 种，实测生成 5000 份记录
#: 就有 167 次重复。重复本身不泄露什么（A 记录的"客户1"和 B 记录的"客户1"是
#: 不同实体），但让相同 token 跨记录出现是白送给外部服务的关联信号，没必要。
_NONCE_LEN = 8


def _restore_pattern(nonce: str) -> re.Pattern[str]:
    """还原时对模型的排版改动留容错：它可能写成 [客户1·a7f3] 或 【客户 1·a7f3】。

    但 nonce 必须匹配——容错的是括号和空格，不是身份。
    """
    labels = "|".join(re.escape(v) for v in ENTITY_LABELS.values())
    return re.compile(
        r"[〔\[【（(]\s*(" + labels + r")\s*(\d+)"
        r"(?::[^〕\]】）)]*)?"          # 金额那种带区间后缀的
        r"·" + re.escape(nonce) + r"\s*[〕\]】）)]"
    )

_ORG_SUFFIXES = (
    "股份有限公司", "有限责任公司", "集团有限公司", "有限公司",
    "分公司", "事业部", "集团", "公司", "厂", "店",
)
_ORG_INDUSTRY = (
    "科技", "技术", "信息", "网络", "电子", "实业", "贸易", "医疗", "教育",
    "智能", "数据", "软件", "系统", "通信", "能源", "物流", "供应链", "咨询", "服务",
)

#: 中文公司简称通常是开头 2-4 字的品牌部分（"阿尔法智能科技有限公司" → "阿尔法"）。
#: 只剥后缀得不到它——后缀剥完还剩 "阿尔法智能"，而正文里写的是 "阿尔法"。
_ORG_PREFIX_LENGTHS = (4, 3, 2)

#: 这些前缀太泛，替换掉会误伤大量无关文本（"中国的市场"、"北京出差"）。
#: 过度脱敏优先是原则，但原则不该退化成把常用词全抹掉。
_ORG_PREFIX_STOPWORDS = frozenset(
    {
        "中国", "中华", "国际", "全球", "全国", "环球", "东方", "华夏",
        "北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "武汉", "西安", "天津",
        "华东", "华南", "华北", "华中", "西南", "东北",
        "第一", "第二", "新型", "现代", "未来",
    }
)
_PERSON_TITLES = ("总", "经理", "先生", "女士", "老板", "总监", "主管")
_PERSON_PREFIXES = ("小", "老")

_CJK = re.compile(r"^[一-鿿]{2,4}$")


@dataclass(frozen=True)
class KnownValue:
    """来自结构化字段的真实值——这是"知道"，不是"猜"。"""

    kind: EntityKind
    value: str
    field_key: str = ""


@dataclass
class Placeholder:
    token: str
    kind: EntityKind
    original: str
    index: int


@dataclass
class Finding:
    """审计摘要。**只记类别与数量，不记原值**。"""

    kind: EntityKind
    layer: str          # known_value | detector | field_rule
    field_key: str
    count: int


@dataclass
class RedactionResult:
    fields: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    #: 假名 token -> 原值。仅内存。
    mapping: dict[str, Placeholder] = field(default_factory=dict)
    #: 被字段策略挡下、根本没进 payload 的字段
    blocked_fields: list[str] = field(default_factory=list)
    policy_version: int = 0
    level: str = "custom"
    redacted: bool = False

    def audit_summary(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        for item in self.findings:
            by_kind[str(item.kind)] = by_kind.get(str(item.kind), 0) + item.count
        return {
            "policyVersion": self.policy_version,
            "level": self.level,
            "redacted": self.redacted,
            "blockedFields": sorted(self.blocked_fields),
            "hitsByKind": dict(sorted(by_kind.items())),
            "placeholderCount": len(self.mapping),
        }


def _org_variants(value: str) -> list[str]:
    """华为技术有限公司 → {华为技术有限公司, 华为技术, 华为}

    三步：剥公司后缀 → 剥行业词 → 取品牌前缀。
    前缀这一步是必须的：正文里写的往往只是 "阿尔法"，而
    "阿尔法智能科技有限公司" 剥完后缀和行业词还剩 "阿尔法智能"，对不上。
    """
    out = {value}
    stem = value
    for suffix in _ORG_SUFFIXES:
        if stem.endswith(suffix) and len(stem) > len(suffix) + 1:
            stem = stem[: -len(suffix)]
            out.add(stem)
            break
    # 行业词可能叠着写（"智能科技"），循环剥到剥不动为止
    changed = True
    while changed:
        changed = False
        for word in _ORG_INDUSTRY:
            if stem.endswith(word) and len(stem) - len(word) >= 2:
                stem = stem[: -len(word)]
                out.add(stem)
                changed = True
                break

    for length in _ORG_PREFIX_LENGTHS:
        if len(stem) > length:
            prefix = stem[:length]
            if prefix not in _ORG_PREFIX_STOPWORDS:
                out.add(prefix)

    return [v for v in out if len(v) >= 2 and v not in _ORG_PREFIX_STOPWORDS]


def _person_variants(value: str, *, derive: bool) -> list[str]:
    """张伟 → {张伟, 张总, 张经理, 小张, 老张, ...}

    称谓派生会误伤（"张总"未必是张伟），但在一份工作记录的语境里几乎必然是同一个人。
    **过度脱敏的代价远小于漏脱敏**，所以默认开启。
    """
    out = {value}
    if derive and _CJK.match(value):
        surname = value[0]
        out.update(f"{surname}{title}" for title in _PERSON_TITLES)
        out.update(f"{prefix}{surname}" for prefix in _PERSON_PREFIXES)
    return [v for v in out if len(v) >= 2]


def _digits_pattern(value: str) -> re.Pattern[str] | None:
    r"""把号码编成"允许任意分隔符"的正则。

    分隔符不止空格和连字符：`138.0013.8000`、`138，0013，8000`、`138（0013）8000`
    都是自然写法。只认 `[\s-]` 等于漏掉大半——这是第二版实测出来的。
    """
    digits = re.sub(r"\D", "", value)
    if len(digits) < 6:
        return None
    body = rf"[{SEPARATORS}]*".join(re.escape(d) for d in digits)
    return re.compile(rf"(?<![0-9]){body}(?![0-9])")


class Redactor:
    def __init__(self, policy: RedactionPolicy, *, nonce: str | None = None):
        self.policy = policy
        self._counters: dict[EntityKind, int] = {}
        self._by_value: dict[tuple[EntityKind, str], Placeholder] = {}
        self.mapping: dict[str, Placeholder] = {}
        # 每次请求一个新 nonce。参数只为测试可复现，业务代码不要传。
        self.nonce = nonce or secrets.token_hex(_NONCE_LEN // 2)
        # 令牌化的盐。跨记录稳定是 HASH 的目的（"是不是同一个"），
        # 所以盐取自策略版本而不是 nonce；但至少不能是全局无盐可枚举的裸哈希。
        self._hash_salt = f"aoju-redaction-v{policy.version}"
        self._restore_re = _restore_pattern(self.nonce)

    # -- 假名分配 ---------------------------------------------------------

    def _placeholder(self, kind: EntityKind, original: str) -> Placeholder:
        """同一实体在同一份文档里始终拿到同一个编号——模型才追得住指代关系。

        编号**每份文档从 1 开始**，不跨文档复用：复用会让"客户 7"在多份报告之间
        可关联，等于自己削弱了去标识化强度。
        """
        key = (kind, original.strip())
        existing = self._by_value.get(key)
        if existing is not None:
            return existing
        index = self._counters.get(kind, 0) + 1
        self._counters[kind] = index
        token = f"{_OPEN}{ENTITY_LABELS[kind]}{index}·{self.nonce}{_CLOSE}"
        placeholder = Placeholder(token=token, kind=kind, original=original, index=index)
        self._by_value[key] = placeholder
        self.mapping[token] = placeholder
        return placeholder

    # -- 分段替换：避免在已生成的假名内部再匹配一次 -------------------------

    @staticmethod
    def _split(segments: list[str | Placeholder], pattern: re.Pattern[str],
               make: Any) -> tuple[list[str | Placeholder], int]:
        out: list[str | Placeholder] = []
        hits = 0
        for seg in segments:
            if isinstance(seg, Placeholder):
                out.append(seg)
                continue
            cursor = 0
            for match in pattern.finditer(seg):
                replacement = make(match)
                if replacement is None:
                    continue
                if match.start() > cursor:
                    out.append(seg[cursor : match.start()])
                out.append(replacement)
                cursor = match.end()
                hits += 1
            if cursor < len(seg):
                out.append(seg[cursor:])
        return out, hits

    @staticmethod
    def _join(segments: list[str | Placeholder]) -> str:
        return "".join(s.token if isinstance(s, Placeholder) else s for s in segments)

    # -- 各层 -------------------------------------------------------------

    def _apply_known_values(
        self, segments: list[str | Placeholder], known: list[KnownValue], field_key: str
    ) -> tuple[list[str | Placeholder], list[Finding]]:
        """L2：把结构化字段里的真实值在正文里替换掉。

        长值优先，否则 `华为技术有限公司` 会被 `华为` 先切成 `〔客户1〕技术有限公司`。
        """
        findings: list[Finding] = []
        expanded: list[tuple[str, KnownValue, re.Pattern[str]]] = []

        for item in known:
            value = (item.value or "").strip()
            if not value or value in self.policy.allow_terms:
                continue
            if item.kind in (EntityKind.PHONE, EntityKind.ID_CARD, EntityKind.BANK_CARD):
                pattern = _digits_pattern(value)
                if pattern is not None:
                    expanded.append((value, item, pattern))
                tail = re.sub(r"\D", "", value)[-4:]
                if len(tail) == 4:
                    expanded.append((
                        value, item,
                        re.compile(r"(?:尾号|末四位|后四位|尾数)\s*[:：]?\s*" + re.escape(tail) + r"(?![0-9])"),
                    ))
                continue
            if item.kind == EntityKind.ORG:
                variants = _org_variants(value) if self.policy.derive_org_prefixes else [value]
            elif item.kind == EntityKind.PERSON:
                variants = _person_variants(value, derive=self.policy.derive_person_aliases)
            else:
                variants = [value]
            for variant in variants:
                if variant in self.policy.allow_terms:
                    continue
                expanded.append((variant, item, re.compile(re.escape(variant))))

        expanded.sort(key=lambda triple: len(triple[0]), reverse=True)

        for _variant, item, pattern in expanded:
            placeholder = self._placeholder(item.kind, item.value.strip())
            segments, hits = self._split(segments, pattern, lambda _m, p=placeholder: p)
            if hits:
                findings.append(
                    Finding(kind=item.kind, layer="known_value", field_key=field_key, count=hits)
                )
        return segments, findings

    def _apply_detectors(
        self, segments: list[str | Placeholder], field_key: str
    ) -> tuple[list[str | Placeholder], list[Finding]]:
        """L3：模式兜底。只处理策略里开启的类别，外加永远不许出云的两类。"""
        findings: list[Finding] = []

        # "尾号 8000" 要在通用数字规则之前，否则 8000 会被别的规则吃掉
        segments, hits = self._split(
            segments,
            PHONE_TAIL_PATTERN,
            lambda m: self._placeholder(EntityKind.PHONE, m.group(0)),
        )
        if hits:
            findings.append(Finding(EntityKind.PHONE, "detector", field_key, hits))

        for detector in DETECTORS:
            if detector.kind not in self.policy.detectors and detector.kind not in ALWAYS_BLOCKED:
                continue
            segments, hits = self._split(
                segments,
                detector.pattern,
                lambda m, d=detector: (
                    None
                    if m.group(0) in self.policy.allow_terms
                    or (d.validator is not None and not d.validator(m.group(0)))
                    else self._placeholder(d.kind, m.group(0))
                ),
            )
            if hits:
                findings.append(Finding(detector.kind, "detector", field_key, hits))

        if self.policy.generalize_amount_in_text:
            segments, hits = self._split(segments, AMOUNT_PATTERN, self._generalize_amount)
            if hits:
                findings.append(Finding(EntityKind.AMOUNT, "detector", field_key, hits))

        return segments, findings

    def _generalize_amount(self, match: re.Match[str]) -> Placeholder | None:
        wan = amount_to_wan(match.group(1), match.group(2))
        if wan is None:
            return None
        placeholder = self._placeholder(EntityKind.AMOUNT, match.group(0))
        # 泛化：假名显示区间，还原时换回原值
        placeholder.token = (
            f"{_OPEN}{ENTITY_LABELS[EntityKind.AMOUNT]}{placeholder.index}"
            f":{bucket_amount(wan)}·{self.nonce}{_CLOSE}"
        )
        self.mapping[placeholder.token] = placeholder
        return placeholder

    # -- 对外接口 ---------------------------------------------------------

    def redact_text(
        self, text: str, *, known_values: list[KnownValue] | None = None, field_key: str = ""
    ) -> tuple[str, list[Finding]]:
        if self.policy.level == "off":
            return text, []
        source = normalize_for_match(text)
        segments: list[str | Placeholder] = [source] if source else []
        findings: list[Finding] = []

        segments, hits = self._apply_known_values(segments, known_values or [], field_key)
        findings.extend(hits)
        segments, hits = self._apply_detectors(segments, field_key)
        findings.extend(hits)

        return self._join(segments), findings

    def redact_document(
        self,
        *,
        fields: dict[str, str],
        known_values: list[KnownValue] | None = None,
    ) -> RedactionResult:
        """按策略处理一整份文档。**未在策略里声明的字段不会出现在结果里。**"""
        if self.policy.level == "off":
            return RedactionResult(
                fields=dict(fields),
                policy_version=self.policy.version,
                level=self.policy.level,
                redacted=False,
            )

        result = RedactionResult(
            mapping=self.mapping,
            policy_version=self.policy.version,
            level=self.policy.level,
        )
        known = list(known_values or [])

        for key, raw in fields.items():
            rule = self.policy.rule_for(key)

            if rule.action == Action.BLOCK:
                result.blocked_fields.append(key)
                continue

            if rule.action == Action.HASH:
                # 身份证、银行卡不能用哈希"代替"阻断：取值空间可枚举，
                # 无盐哈希还跨记录稳定可关联——那不是阻断，是换了个形式的标识符。
                if rule.kind in ALWAYS_BLOCKED:
                    result.blocked_fields.append(key)
                    continue
                digest = hashlib.sha256(
                    f"{self._hash_salt}\x00{raw or ''}".encode()
                ).hexdigest()[:16]
                result.fields[key] = f"{_OPEN}令牌:{digest}{_CLOSE}"
                continue

            if rule.action == Action.GENERALIZE and rule.kind == EntityKind.AMOUNT:
                match = AMOUNT_PATTERN.search(normalize_for_match(raw))
                wan = amount_to_wan(match.group(1), match.group(2)) if match else None
                result.fields[key] = bucket_amount(wan) if wan is not None else ""
                result.findings.append(Finding(EntityKind.AMOUNT, "field_rule", key, 1))
                continue

            if rule.action == Action.PSEUDONYMIZE and rule.kind is not None:
                value = str(raw or "").strip()
                if value:
                    placeholder = self._placeholder(rule.kind, value)
                    result.fields[key] = placeholder.token
                    result.findings.append(Finding(rule.kind, "field_rule", key, 1))
                else:
                    result.fields[key] = ""
                continue

            # PASS：仍然要过 L2/L3——自由文本里可能夹带别的字段的敏感值
            redacted, findings = self.redact_text(raw, known_values=known, field_key=key)
            result.fields[key] = redacted
            result.findings.extend(findings)

        result.redacted = bool(
            result.blocked_fields or result.findings or result.fields != fields
        )
        return result

    # -- 返回路径 ---------------------------------------------------------

    def restore(self, value: Any) -> Any:
        """把模型返回内容里的假名换回真实值。

        不做这一步，人看到的证据引用就和他眼里的原文对不上，"可解释"的承诺整个作废。
        对模型的排版改动留容错：`[客户1]`、`【客户 1】` 都能还原。
        """
        if isinstance(value, str):
            return self._restore_text(value)
        if isinstance(value, dict):
            return {k: self.restore(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.restore(v) for v in value]
        return value

    def _restore_text(self, text: str) -> str:
        # 先按精确 token 还原（含金额那种带区间后缀的）
        out = str(text or "")
        for token, placeholder in sorted(self.mapping.items(), key=lambda kv: -len(kv[0])):
            if token in out:
                out = out.replace(token, placeholder.original)

        # 再按"标签+序号"容错还原模型改过排版的写法
        def _sub(match: re.Match[str]) -> str:
            label, index = match.group(1), int(match.group(2))
            for placeholder in self.mapping.values():
                if ENTITY_LABELS[placeholder.kind] == label and placeholder.index == index:
                    return placeholder.original
            return match.group(0)

        return self._restore_re.sub(_sub, out)
