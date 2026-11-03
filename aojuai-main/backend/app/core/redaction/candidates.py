"""候选实体识别：把"猜"升级成"知道"的那一步，但**不调用任何外部模型**。

为什么不是让用户填结构化表单：填表正是这类产品要消除的摩擦，在手机上尤其如此。
更好的做法是**候选 + 一次点选**——本地识别出可疑片段，在正文里标出来，
用户点一下选"客户名 / 联系人 / 无关"：

- 没识别到东西时，用户零额外操作
- 识别到时，一次点击就把"猜"升级成"知道"，L2 从此按真值精确替换
- 用户不点也不影响：该假名化的照样假名化，只是精度低一些

识别**绝不能调用外部模型**——那就成了"为了脱敏先把原文发出去"，逻辑上是自相矛盾的。

置信度只分两档，因为它只影响 UI 怎么呈现，不影响安全性：
- `high`：手机号、邮箱这类有确定格式的。它们**不需要用户确认**，本来就会被脱敏，
  这里返回只是为了让用户看见"系统注意到了"。
- `medium`：靠后缀猜的机构名、靠称谓猜的人名。这些**需要用户确认**，
  确认之后才会进入 L2 的已知值。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .detectors import DETECTORS, normalize_for_match
from .policy import EntityKind

#: 机构名：靠后缀锚定。中文里"XX有限公司"几乎不会误判，
#: 而"XX科技"这类短后缀会有噪声——所以标 medium，交给用户裁决。
_ORG_SUFFIX = r"(?:股份有限公司|有限责任公司|有限公司|集团|控股|科技|技术|实业|贸易|医院|学校|银行|公司)"
_ORG_RE = re.compile(rf"[一-鿿A-Za-z0-9]{{2,20}}{_ORG_SUFFIX}")

#: 人名：中文姓名没有词边界，直接猜会大量误伤（"张伟"和普通词同形）。
#: 只认**称谓**形式——"张总""李经理"在工作记录里是高信号的人物指代。
_PERSON_RE = re.compile(r"[一-鿿]{1,2}(?:总经理|总监|经理|主管|老板|总|先生|女士)")

#: 这些词看着像机构名，但几乎总是泛指，不该弹给用户确认。
_ORG_STOPWORDS = frozenset(
    {"公司", "集团", "科技", "技术", "实业", "贸易", "分公司", "总公司", "对方公司", "我们公司", "本公司"}
)


#: 中文里名字前面常粘着时间词、动词和虚词——"上午拜访华为技术有限公司"、"的李经理"。
#: 正则往左是贪心的，框出来会带一串前缀。这里从左边逐个裁掉。
#:
#: 这是启发式的，裁不干净也没关系：**框得准不准只影响体验，不影响安全**——
#: 安全由脱敏本身保证，不由高亮保证。用户点选时看到的是自己写的原文，
#: 多一个字少一个字他一眼就能判断。
_LEADING_NOISE: tuple[str, ...] = (
    "上午", "下午", "今天", "明天", "昨天", "早上", "晚上", "今日", "明日", "全天",
    "拜访", "回访", "联系", "对接", "沟通", "签约", "跟进", "电话", "见了", "约了", "谈了",
    "去了", "到了", "找了", "陪同", "带着", "介绍",
)
_LEADING_PARTICLES = frozenset("的和与跟在给对从把被及了过向为由让并且但也还就再又都")

#: 裁完之后短于这个长度就不算候选——剩下一两个字通常是裁过头或本来就是噪声。
_MIN_ENTITY_LEN = 2


def _trim_leading(value: str) -> str:
    text = value
    changed = True
    while changed and len(text) > _MIN_ENTITY_LEN:
        changed = False
        for noise in _LEADING_NOISE:
            if text.startswith(noise) and len(text) - len(noise) >= _MIN_ENTITY_LEN:
                text = text[len(noise) :]
                changed = True
                break
        while (
            len(text) > _MIN_ENTITY_LEN
            and text[0] in _LEADING_PARTICLES
        ):
            text = text[1:]
            changed = True
    return text


@dataclass(frozen=True)
class Candidate:
    field_key: str
    start: int
    end: int
    text: str
    kind: EntityKind
    confidence: str          # high | medium
    #: high 的项系统会自动处理，不需要用户表态
    needs_confirmation: bool


def find_candidates(fields: dict[str, str]) -> list[Candidate]:
    """在自由文本里找出可能的实体。位置是**规范化后文本**上的偏移。

    偏移用于前端高亮。规范化（NFKC）对中文与半角字符是长度不变的，全角数字折成
    半角也是 1:1，所以偏移可以直接用；真出现长度变化的冷门字符（㈱ 之类），
    最坏结果只是高亮偏了一格，不影响安全性——安全由脱敏本身保证，不由高亮保证。
    """
    found: list[Candidate] = []

    for field_key, raw in (fields or {}).items():
        text = normalize_for_match(raw)
        if not text:
            continue
        taken: list[tuple[int, int]] = []

        def overlaps(start: int, end: int) -> bool:
            return any(not (end <= s or start >= e) for s, e in taken)

        # 有确定格式的先占位，避免机构名规则把号码的一部分吃进去
        for detector in DETECTORS:
            for match in detector.pattern.finditer(text):
                if overlaps(match.start(), match.end()):
                    continue
                taken.append((match.start(), match.end()))
                found.append(
                    Candidate(
                        field_key=field_key,
                        start=match.start(),
                        end=match.end(),
                        text=match.group(0),
                        kind=detector.kind,
                        confidence="high",
                        needs_confirmation=False,
                    )
                )

        for match in _ORG_RE.finditer(text):
            trimmed = _trim_leading(match.group(0))
            start = match.end() - len(trimmed)
            if trimmed in _ORG_STOPWORDS or len(trimmed) < _MIN_ENTITY_LEN:
                continue
            if overlaps(start, match.end()):
                continue
            taken.append((start, match.end()))
            found.append(
                Candidate(
                    field_key=field_key,
                    start=start,
                    end=match.end(),
                    text=trimmed,
                    kind=EntityKind.ORG,
                    confidence="medium",
                    needs_confirmation=True,
                )
            )

        for match in _PERSON_RE.finditer(text):
            trimmed = _trim_leading(match.group(0))
            start = match.end() - len(trimmed)
            if len(trimmed) < _MIN_ENTITY_LEN or overlaps(start, match.end()):
                continue
            taken.append((start, match.end()))
            found.append(
                Candidate(
                    field_key=field_key,
                    start=start,
                    end=match.end(),
                    text=trimmed,
                    kind=EntityKind.PERSON,
                    confidence="medium",
                    needs_confirmation=True,
                )
            )

    found.sort(key=lambda c: (c.field_key, c.start))
    return found
