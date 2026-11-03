"""Vocabulary and limits owned by the support capability.

分类取值刻意是**通用客服口径**（咨询 / 故障 / 计费 / 建议 / 其他），不带任何行业词汇：
上游分支要自己的口径时改这一处即可，而不是让基座认识某条业务线。

前端不显示这些字面量，只用它们查 `support.category.<value>` 之类的语言包键——
所以 `/options` 只返回取值，不返回服务端中文标签（返回标签就等于 en/es 界面漏中文）。
"""

from __future__ import annotations

CATEGORIES: tuple[str, ...] = ("question", "incident", "billing", "feature", "other")
STATUSES: tuple[str, ...] = ("open", "pending", "resolved", "closed")
PRIORITIES: tuple[str, ...] = ("low", "normal", "high", "urgent")

DEFAULT_CATEGORY = "other"
DEFAULT_STATUS = "open"
DEFAULT_PRIORITY = "normal"

#: 终态：已解决 / 已关闭的工单不再自动回到"等待客服"。
TERMINAL_STATUSES: frozenset[str] = frozenset({"resolved", "closed"})

#: 首次响应 SLA（小时）。做成模块常量而不是 Settings 项：能力包要能整目录拷进空基座，
#: 往 `core/config.py` 加字段会让"自包含"这条不成立。租户级可调时再走模块设置入口。
DEFAULT_SLA_HOURS = 24

#: 匿名提单限流：同一来源 IP 每 10 分钟最多 5 次。
PUBLIC_SUBMIT_WINDOW_SECONDS = 600
PUBLIC_SUBMIT_MAX_PER_WINDOW = 5

#: 公开留言桥接进来的工单统一打这个 related_type，客服端可据此筛选来源。
PUBLIC_CONTACT_RELATED_TYPE = "public_contact"

__all__ = [
    "CATEGORIES",
    "DEFAULT_CATEGORY",
    "DEFAULT_PRIORITY",
    "DEFAULT_SLA_HOURS",
    "DEFAULT_STATUS",
    "PRIORITIES",
    "PUBLIC_CONTACT_RELATED_TYPE",
    "PUBLIC_SUBMIT_MAX_PER_WINDOW",
    "PUBLIC_SUBMIT_WINDOW_SECONDS",
    "STATUSES",
    "TERMINAL_STATUSES",
]
