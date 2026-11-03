"""脱敏策略：哪些字段能出云、以什么形态出云。

策略是 allowlist：**没有在 field_rules 里声明的字段一律不发送**。
新增字段时如果没人来给它定性，它默认出不去——这正是我们要的默认值。

设计与取舍见 `docs/dev/reference/LLM_OUTBOUND_REDACTION.md`。
本模块不出现任何业务词汇，将来可整体上收到底座。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal, cast

POLICY_SCHEMA_VERSION = 1

RedactionLevel = Literal["off", "basic", "standard", "strict", "custom"]
PresetBaseLevel = Literal["off", "basic", "standard", "strict"]
_LEVELS = frozenset({"off", "basic", "standard", "strict", "custom"})
_BASE_LEVELS = frozenset({"off", "basic", "standard", "strict"})


class EntityKind(StrEnum):
    """实体类别。决定假名的标签，也决定守卫的严格程度。"""

    PERSON = "person"
    ORG = "org"
    PHONE = "phone"
    EMAIL = "email"
    ID_CARD = "id_card"
    BANK_CARD = "bank_card"
    SERIAL = "serial"
    ADDRESS = "address"
    AMOUNT = "amount"


#: 假名里显示的中文标签。用中文是因为模型在中文语境下更容易理解它是什么。
ENTITY_LABELS: dict[EntityKind, str] = {
    EntityKind.PERSON: "联系人",
    EntityKind.ORG: "客户",
    EntityKind.PHONE: "手机",
    EntityKind.EMAIL: "邮箱",
    EntityKind.ID_CARD: "身份证",
    EntityKind.BANK_CARD: "卡号",
    EntityKind.SERIAL: "编号",
    EntityKind.ADDRESS: "地址",
    EntityKind.AMOUNT: "金额",
}

#: 无论策略怎么配都不允许出云的类别。身份证和银行卡没有任何"模型需要看到"的理由。
ALWAYS_BLOCKED: frozenset[EntityKind] = frozenset(
    {EntityKind.ID_CARD, EntityKind.BANK_CARD}
)


#: 默认开启的探测器。策略里不写 detectors 时用它——"没写"不等于"一个都不要"。
_DEFAULT_DETECTORS: frozenset[EntityKind] = frozenset(
    {
        EntityKind.PHONE,
        EntityKind.EMAIL,
        EntityKind.ID_CARD,
        EntityKind.BANK_CARD,
        EntityKind.SERIAL,
    }
)


class Action(StrEnum):
    """对一个字段/实体做什么。对应 ISO/IEC 20889 的几类去标识化手法。"""

    PASS = "pass"                # 原样发送
    PSEUDONYMIZE = "pseudonymize"  # 假名化，可还原
    GENERALIZE = "generalize"    # 泛化（金额→区间）
    HASH = "hash"                # 令牌化，不可还原
    BLOCK = "block"              # 抑制，且正文里出现也要清掉


@dataclass(frozen=True)
class FieldRule:
    action: Action
    kind: EntityKind | None = None
    note: str = ""


#: 金额泛化的区间。保留量级（评分需要判断"大单还是小单"），去掉精确值。
AMOUNT_BUCKETS: tuple[tuple[float, str], ...] = (
    (1, "1万以下"),
    (5, "1万-5万"),
    (10, "5万-10万"),
    (50, "10万-50万"),
    (100, "50万-100万"),
    (500, "100万-500万"),
)
AMOUNT_BUCKET_TOP = "500万以上"


@dataclass(frozen=True)
class RedactionPolicy:
    """一份可版本化、可签字的策略。"""

    version: int = 0
    schema_version: int = POLICY_SCHEMA_VERSION
    #: `custom` 以 base_level 对应的预设为底再叠高级覆盖；旧版无 level 的策略按 custom 兼容读取。
    level: RedactionLevel = "custom"
    base_level: PresetBaseLevel | None = None

    #: 结构化字段 → 规则。**不在此表里的字段不发送**（allowlist）。
    field_rules: dict[str, FieldRule] = field(default_factory=dict)

    #: L3 模式探测开关。关掉某类只是关掉"猜"，L4 守卫仍然会拦。
    detectors: frozenset[EntityKind] = field(
        default_factory=lambda: frozenset(_DEFAULT_DETECTORS)
    )

    #: 是否在自由文本里泛化金额。默认关：中文里"签约 2 家""跟进 5 个"太容易误伤，
    #: 而结构化的金额字段走 field_rules 就够了。租户确认后可开。
    generalize_amount_in_text: bool = False

    #: 从姓名派生称谓别名（张伟 → 张总/小张）。默认开——过度脱敏的代价远小于漏脱敏。
    derive_person_aliases: bool = True

    #: 机构名剥离后缀后再取前缀匹配（华为技术有限公司 → 华为技术 → 华为）。
    derive_org_prefixes: bool = True

    #: 允许原样出云的词。用于压误报（自家产品名、行业通用词）。
    allow_terms: frozenset[str] = field(default_factory=frozenset)

    #: 守卫命中后的动作。默认 reject —— "尽力清理后照发"在合规上等于没有承诺。
    guard_on_violation: str = "reject"

    approved_by: str = ""
    approved_at: str = ""
    note: str = ""

    @classmethod
    def preset(cls, level: RedactionLevel) -> RedactionPolicy:
        """返回不含字段规则的内置档位。业务字段 allowlist 必须由模块或租户显式提供。"""
        if level not in _LEVELS:
            raise ValueError(f"unknown redaction level: {level!r}")

        strong = frozenset(
            {
                EntityKind.PHONE,
                EntityKind.ID_CARD,
                EntityKind.BANK_CARD,
                EntityKind.EMAIL,
            }
        )
        if level == "off":
            return cls(
                level="off",
                detectors=frozenset(),
                derive_person_aliases=False,
                derive_org_prefixes=False,
                generalize_amount_in_text=False,
                guard_on_violation="warn",
            )
        if level == "basic":
            return cls(
                level="basic",
                detectors=strong,
                derive_person_aliases=False,
                derive_org_prefixes=False,
                generalize_amount_in_text=False,
                guard_on_violation="warn",
            )

        standard_detectors = strong | {
            EntityKind.PERSON,
            EntityKind.ORG,
            EntityKind.ADDRESS,
            # 合同号 / 订单号 / 单据号这类业务编号同样能定位到具体客户，标准档就要抓（与引入前的模块默认一致）
            EntityKind.SERIAL,
        }
        if level == "standard":
            return cls(
                level="standard",
                detectors=frozenset(standard_detectors),
                derive_person_aliases=True,
                derive_org_prefixes=True,
                generalize_amount_in_text=False,
                guard_on_violation="reject",
            )
        if level == "strict":
            return cls(
                level="strict",
                detectors=frozenset(standard_detectors),
                derive_person_aliases=True,
                derive_org_prefixes=True,
                generalize_amount_in_text=True,
                allow_terms=frozenset(),
                guard_on_violation="reject",
            )

        # custom 没有独立的安全语义；缺省从 standard 出发，调用方可在 JSON 中记录 baseLevel。
        standard = cls.preset("standard")
        return cls(
            level="custom",
            base_level="standard",
            detectors=standard.detectors,
            derive_person_aliases=standard.derive_person_aliases,
            derive_org_prefixes=standard.derive_org_prefixes,
            generalize_amount_in_text=standard.generalize_amount_in_text,
            allow_terms=standard.allow_terms,
            guard_on_violation=standard.guard_on_violation,
        )

    def rule_for(self, field_key: str) -> FieldRule:
        """未声明 = 不发送。这一句就是 allowlist 本身。"""
        return self.field_rules.get(field_key) or FieldRule(
            action=Action.BLOCK, note="字段未在策略中声明"
        )

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schemaVersion": self.schema_version,
            "level": self.level,
            "fieldRules": {
                key: {"action": str(rule.action), "kind": str(rule.kind) if rule.kind else None,
                      "note": rule.note}
                for key, rule in self.field_rules.items()
            },
            "detectors": sorted(str(k) for k in self.detectors),
            "generalizeAmountInText": self.generalize_amount_in_text,
            "derivePersonAliases": self.derive_person_aliases,
            "deriveOrgPrefixes": self.derive_org_prefixes,
            "allowTerms": sorted(self.allow_terms),
            "guardOnViolation": self.guard_on_violation,
            "approvedBy": self.approved_by,
            "approvedAt": self.approved_at,
            "note": self.note,
        }
        if self.level == "custom" and self.base_level is not None:
            payload["baseLevel"] = self.base_level
        return payload

    @classmethod
    def from_json(cls, payload: dict[str, Any], *, version: int = 0) -> RedactionPolicy:
        raw_level = str(payload.get("level") or "").strip().lower()
        if raw_level in _LEVELS:
            level = cast(RedactionLevel, raw_level)
            if level == "custom":
                raw_base_level = str(payload.get("baseLevel") or "standard").strip().lower()
                base_level = cast(
                    PresetBaseLevel,
                    raw_base_level if raw_base_level in _BASE_LEVELS else "standard",
                )
                base = cls.preset(base_level)
            else:
                base_level = None
                base = cls.preset(level)
        else:
            # 已落库的 v1 策略没有 level；保留原有缺省语义，读取后标为 custom。
            level = "custom"
            base_level = None
            base = cls()

        raw_rules = payload.get("fieldRules") or {}
        if not isinstance(raw_rules, dict):
            raw_rules = {}
        rules: dict[str, FieldRule] = {}
        for key, item in raw_rules.items():
            if not isinstance(item, dict):
                # 认不出的条目按最保守的来。整条丢掉会让 rule_for 走"未声明 → BLOCK"，
                # 结果一样，但显式写出来意图更清楚。
                rules[str(key)] = FieldRule(action=Action.BLOCK, note="策略条目格式错误")
                continue
            try:
                action = Action(str(item.get("action")))
            except ValueError:
                action = Action.BLOCK   # 认不出的动作不要"当作 pass 放行"
            kind_raw = item.get("kind")
            try:
                kind = EntityKind(str(kind_raw)) if kind_raw else None
            except ValueError:
                kind = None

            # pseudonymize / generalize 都需要知道这是什么类别才能执行。
            # kind 缺失或写错时**不能退回原样发送**——那是配错了却看起来在保护，
            # 比不保护更危险。降级成 BLOCK。
            if action in (Action.PSEUDONYMIZE, Action.GENERALIZE) and kind is None:
                rules[str(key)] = FieldRule(
                    action=Action.BLOCK, note=f"{action} 缺少有效的 kind，已降级为不发送"
                )
                continue

            rules[str(key)] = FieldRule(action=action, kind=kind, note=str(item.get("note") or ""))

        # detectors 没写 ≠ 一个都不要。带 level 时继承预设；旧策略继承历史默认集合。
        raw_detectors = payload.get("detectors")
        if raw_detectors is None:
            detectors = set(base.detectors)
        elif isinstance(raw_detectors, (list, tuple, set, frozenset)):
            detectors = set()
            for raw in raw_detectors:
                try:
                    detectors.add(EntityKind(str(raw)))
                except ValueError:
                    continue
        else:
            detectors = set(base.detectors)

        guard = str(payload.get("guardOnViolation") or base.guard_on_violation)
        if guard not in ("reject", "redact", "warn"):
            guard = base.guard_on_violation

        try:
            schema_version = int(payload.get("schemaVersion") or POLICY_SCHEMA_VERSION)
        except (TypeError, ValueError):
            schema_version = POLICY_SCHEMA_VERSION

        raw_allow_terms = payload.get("allowTerms", base.allow_terms)
        if isinstance(raw_allow_terms, str):
            raw_allow_terms = [raw_allow_terms]
        elif not isinstance(raw_allow_terms, (list, tuple, set, frozenset)):
            raw_allow_terms = base.allow_terms

        return cls(
            version=version,
            schema_version=schema_version,
            level=level,
            base_level=base_level,
            field_rules=rules,
            detectors=frozenset(detectors),
            generalize_amount_in_text=bool(
                payload.get("generalizeAmountInText", base.generalize_amount_in_text)
            ),
            derive_person_aliases=bool(
                payload.get("derivePersonAliases", base.derive_person_aliases)
            ),
            derive_org_prefixes=bool(
                payload.get("deriveOrgPrefixes", base.derive_org_prefixes)
            ),
            allow_terms=frozenset(
                str(t) for t in raw_allow_terms if str(t).strip()
            ),
            guard_on_violation=guard,
            approved_by=str(payload.get("approvedBy") or ""),
            approved_at=str(payload.get("approvedAt") or ""),
            note=str(payload.get("note") or ""),
        )


def preset(level: RedactionLevel) -> RedactionPolicy:
    """函数式入口，便于配置/API 代码直接构造内置档位。"""
    return RedactionPolicy.preset(level)


def bucket_amount(value: float) -> str:
    for ceiling, label in AMOUNT_BUCKETS:
        if value < ceiling:
            return label
    return AMOUNT_BUCKET_TOP
