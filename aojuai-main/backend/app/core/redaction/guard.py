"""L4 出站守卫：payload 交给 HTTP 客户端之前的最后一眼。

**这一层是独立实现，故意不复用 detectors.py 的规则对象。**
纵深防御的最后一层如果和前面共用同一个错误前提，它会和前面一起失效——
本能力的第一版就是全仓统一用 `\\b`，于是"两层保护"实际上是一层，而且是漏的那一层。

它的做法与 L3 刻意不同：**先把所有分隔符抽掉、只看纯数字串，再按长度和特征判类别**，
不依赖任何边界断言、不依赖具体的分隔符写法。

一个实测出来的坑：不能整段贪心地取"数字串"再按总长度判断。
`联系13800138000 2次` 会被合并成 12 位，然后因为"12 位既不是手机也不是卡号"
被整段忽略——手机号就这么漏过去了。所以要在数字串上**滑窗**，
只要存在任意一段 11 位符合手机号特征就算命中。

三条纪律：
1. **只判有无，不做修补。** 职责越小越不容易错。
2. **fail closed。** 命中就抛异常、不发送。默认 reject 而不是 redact——
   "尽力清理后照发"在合规上等于没有承诺。
3. **不回显原值。** 报告里只有类别和位置，异常信息会一路传到前端。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .policy import EntityKind, RedactionPolicy


class RedactionBlocked(Exception):
    """守卫拦截。调用方必须让用户能"不使用 AI 直接提交"，不能变成死路。"""

    def __init__(self, violations: list[GuardViolation]):
        self.violations = violations
        parts = "；".join(f"{v.field_key or '内容'} 疑似包含{v.label}" for v in violations)
        super().__init__(f"内容中仍存在未脱敏的敏感信息：{parts}")


@dataclass(frozen=True)
class GuardViolation:
    kind: EntityKind
    label: str
    field_key: str
    #: 在该字段中的字符位置。**不带原值**。
    position: int


_LABELS = {
    EntityKind.PHONE: "手机号",
    EntityKind.ID_CARD: "身份证号",
    EntityKind.BANK_CARD: "银行卡号",
    EntityKind.EMAIL: "邮箱地址",
}

_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}")

#: 中文数字也要折成阿拉伯数字——NFKC 不管这个，而"一三八〇〇一三八〇〇〇"
#: 是正常人写得出来的。
_CN_DIGITS = {
    "〇": "0", "零": "0", "○": "0", "一": "1", "壹": "1", "幺": "1",
    "二": "2", "贰": "2", "两": "2", "三": "3", "叁": "3", "四": "4", "肆": "4",
    "五": "5", "伍": "5", "六": "6", "陆": "6", "七": "7", "柒": "7",
    "八": "8", "捌": "8", "九": "9", "玖": "9",
}

#: 数字之间可能夹的东西。范围比 L3 更宽——守卫宁可多拦，不可漏放。
_JOINERS = " \t\r\n -.,，。、·_/()（）[]【】<>《》"

_MOBILE = re.compile(r"1[3-9]\d{9}")
_ID_TAIL = re.compile(r"\d{17}[\dXx]")


def _fold(text: str) -> str:
    """NFKC → 去不可见字符 → 中文数字转阿拉伯数字。"""
    folded = unicodedata.normalize("NFKC", str(text or ""))
    folded = "".join(ch for ch in folded if unicodedata.category(ch) not in ("Cf", "Mn"))
    return "".join(_CN_DIGITS.get(ch, ch) for ch in folded)


def _digit_runs(text: str) -> list[tuple[int, str]]:
    """找出"数字 + 分隔符"的连续片段，返回 (起始位置, 抽掉分隔符后的数字串)。"""
    runs: list[tuple[int, str]] = []
    start: int | None = None
    digits: list[str] = []
    for index, ch in enumerate(text):
        if ch.isdigit():
            if start is None:
                start = index
            digits.append(ch)
        elif ch in _JOINERS and start is not None:
            continue                      # 分隔符：不打断，也不计入
        else:
            if start is not None and digits:
                runs.append((start, "".join(digits)))
            start, digits = None, []
    if start is not None and digits:
        runs.append((start, "".join(digits)))
    return runs


def _scan_digits(text: str, field_key: str) -> list[GuardViolation]:
    found: list[GuardViolation] = []
    for position, digits in _digit_runs(text):
        length = len(digits)
        kind: EntityKind | None = None

        # 滑窗：不能只看整段长度，否则"号码后面跟了个业务数字"就整段漏掉
        if any(_MOBILE.fullmatch(digits[i : i + 11]) for i in range(max(0, length - 10))):
            kind = EntityKind.PHONE
        elif 16 <= length <= 19:
            kind = EntityKind.BANK_CARD
        elif length == 18:
            kind = EntityKind.ID_CARD

        if kind is not None:
            found.append(
                GuardViolation(kind=kind, label=_LABELS[kind], field_key=field_key, position=position)
            )

    # 结尾带 X 的身份证：X 不是数字，上面的 run 切不出来，单独扫一遍
    for match in _ID_TAIL.finditer(text):
        found.append(
            GuardViolation(
                kind=EntityKind.ID_CARD,
                label=_LABELS[EntityKind.ID_CARD],
                field_key=field_key,
                position=match.start(),
            )
        )
    return found


def scan(fields: dict[str, str]) -> list[GuardViolation]:
    """扫描最终 payload。返回违规清单，不修改任何内容。"""
    violations: list[GuardViolation] = []
    for key, raw in (fields or {}).items():
        text = _fold(raw)
        violations.extend(_scan_digits(text, key))
        for match in _EMAIL.finditer(text):
            violations.append(
                GuardViolation(
                    kind=EntityKind.EMAIL,
                    label=_LABELS[EntityKind.EMAIL],
                    field_key=key,
                    position=match.start(),
                )
            )
    return violations


def enforce(fields: dict[str, str], policy: RedactionPolicy) -> dict[str, str]:
    """守卫的唯一出口。调用方必须走这里，不能自己拼 payload 直接发。"""
    if policy.level == "off":
        return fields
    violations = scan(fields)
    if not violations:
        return fields
    if policy.guard_on_violation == "warn":
        return fields
    if policy.guard_on_violation == "redact":
        cleaned = dict(fields)
        for key in {v.field_key for v in violations}:
            text = _fold(cleaned.get(key))
            text = _EMAIL.sub("〔已屏蔽〕", text)
            text = re.sub(rf"[0-9][0-9{re.escape(_JOINERS)}]{{5,}}[0-9]", "〔已屏蔽〕", text)
            cleaned[key] = text
        return cleaned
    raise RedactionBlocked(violations)
