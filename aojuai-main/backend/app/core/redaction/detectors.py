"""L3 模式探测：L1/L2 覆盖不到时的兜底。

这一层的定位是**降低守卫的拒绝率**，不是主力。任何时候发现"要靠加正则来保证
安全"，说明字段策略和已知值回扫没做到位。

中文语境下让第一版全漏、以及让第二版仍然漏的坑，逐条记在这里：

1. **不能用 `\\b`。** Python 的 `\\b` 是 `\\w` 与 `\\W` 之间的边界，而中文字符
   在 Unicode 模式下就是 `\\w`——"客户手机13800138000" 里"机"和"1"两边都是 `\\w`，
   边界不成立，规则静默跳过。改用显式的"前后不是数字/字母"环视。
2. **NFKC 不够。** 它能把全角数字折成半角，但**不会**处理零宽字符、变体选择符，
   也**不会**把"一三八〇"变成数字。这三样都是正常人会写出来的东西。
3. **分隔符不止空格和连字符。** `138.0013.8000`、`138，0013，8000`、
   `138（0013）8000` 都是自然写法，只认 `[\\s-]` 等于漏掉大半。
4. **顺序有讲究。** 身份证（18 位）必须排在手机号（11 位）前面，否则会被切走一段；
   银行卡必须排在通用长数字前面。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from .policy import EntityKind

#: 号码里可能出现的分隔符。只认空格和连字符会漏掉大半自然写法。
SEPARATORS = r"\s\-.,，。、·_/()（）\[\]【】"
_SEP = rf"[{SEPARATORS}]*"

#: 前后不是数字/字母的环视。中文、标点、行首行尾都算边界。
_L = r"(?<![0-9A-Za-z])"
_R = r"(?![0-9A-Za-z])"
_LD = r"(?<![0-9])"
_RD = r"(?![0-9])"

#: 中文数字。写"一三八〇〇一三八〇〇〇"的人不多，但一个都挡不住就是零防护。
CN_DIGIT_MAP = {
    "〇": "0", "零": "0", "○": "0", "Ｏ": "0",
    "一": "1", "壹": "1", "幺": "1",
    "二": "2", "贰": "2", "两": "2",
    "三": "3", "叁": "3",
    "四": "4", "肆": "4",
    "五": "5", "伍": "5",
    "六": "6", "陆": "6",
    "七": "7", "柒": "7",
    "八": "8", "捌": "8",
    "九": "9", "玖": "9",
}
_CN_DIGIT_CHARS = "".join(CN_DIGIT_MAP)
_CN_PHONE_RE = re.compile(rf"[{_CN_DIGIT_CHARS}]{{11}}")


def _cn_to_digits(text: str) -> str:
    return "".join(CN_DIGIT_MAP.get(ch, ch) for ch in text)


def _is_cn_mobile(text: str) -> bool:
    digits = _cn_to_digits(text)
    return bool(re.fullmatch(r"1[3-9]\d{9}", digits))


@dataclass(frozen=True)
class Detector:
    kind: EntityKind
    pattern: re.Pattern[str]
    #: 命中之后的二次校验。没有它的话 `[中文数字]{11}` 会把"一二三四五六七八九十一"
    #: 这种句子也当成号码。
    validator: Callable[[str], bool] | None = None
    note: str = ""


#: 顺序即优先级：靠前的先匹配、先占位。
DETECTORS: tuple[Detector, ...] = (
    Detector(EntityKind.EMAIL, re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    # 18 位身份证要在手机号之前
    Detector(EntityKind.ID_CARD, re.compile(rf"{_L}\d{{6}}{_SEP}\d{{8}}{_SEP}\d{{3}}[\dXx]{_R}")),
    Detector(EntityKind.ID_CARD, re.compile(rf"{_L}\d{{17}}[\dXx]{_R}")),
    # 银行卡：16-19 位，允许分隔；要在通用长数字之前
    Detector(EntityKind.BANK_CARD, re.compile(rf"{_LD}\d{{4}}{_SEP}\d{{4}}{_SEP}\d{{4}}{_SEP}\d{{4,7}}{_RD}")),
    # 手机号：允许任意分隔符落在任意位置
    Detector(
        EntityKind.PHONE,
        re.compile(rf"{_LD}1{_SEP}[3-9](?:{_SEP}\d){{9}}{_RD}"),
    ),
    # 中文数字写的手机号
    Detector(EntityKind.PHONE, _CN_PHONE_RE, validator=_is_cn_mobile),
    # 座机
    Detector(EntityKind.PHONE, re.compile(rf"{_LD}0\d{{2,3}}[\s\-]\d{{7,8}}{_RD}")),
    # 字母数字混排的单号，以及连续 8 位以上纯数字
    Detector(EntityKind.SERIAL, re.compile(rf"{_L}[A-Za-z]{{2,}}[\-_]?\d{{6,}}{_R}")),
    Detector(EntityKind.SERIAL, re.compile(rf"{_LD}\d{{8,}}{_RD}")),
)

#: 金额：数字 + 单位。默认不启用（见 policy.generalize_amount_in_text）——
#: 中文里"签约 2 家""跟进 5 个"太容易误伤，而结构化金额走字段策略就够了。
AMOUNT_PATTERN = re.compile(r"(?<![0-9])(\d+(?:\.\d+)?)\s*(万元|万|亿元|亿|元|块)(?![0-9])")

#: "尾号 8000" 这类只写后四位的写法。单独识别，避免把任意 4 位数字都当号码。
PHONE_TAIL_PATTERN = re.compile(r"(尾号|末四位|后四位|尾数)\s*[:：]?\s*(\d{4})(?![0-9])")


def strip_invisible(text: str) -> str:
    """去掉零宽字符、变体选择符这类不可见字符。

    它们对人不可见、对语义没贡献，却能把 `13800138000` 切成正则匹配不到的东西。
    Cf 是格式字符（零宽空格、方向标记），Mn 是非间距记号（变体选择符）。
    """
    return "".join(ch for ch in text if unicodedata.category(ch) not in ("Cf", "Mn"))


def normalize_for_match(text: str) -> str:
    """规范化：NFKC + 去掉不可见字符。

    **NFKC 单独用是不够的**：它折全角、不折零宽。
    结果同时用于匹配与替换（出云内容就是这个规范化后的版本），
    所以不做偏移映射——库里的原文一个字节都不动。
    """
    return strip_invisible(unicodedata.normalize("NFKC", str(text or "")))


def amount_to_wan(number: str, unit: str) -> float | None:
    """把"18万""1.2亿""8000元"统一换算成以万为单位的数值。"""
    try:
        value = float(number)
    except (TypeError, ValueError):
        return None
    if unit in ("万元", "万"):
        return value
    if unit in ("亿元", "亿"):
        return value * 10000
    if unit in ("元", "块"):
        return value / 10000
    return None
