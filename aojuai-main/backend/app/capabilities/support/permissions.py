"""Permission codes are a public API shared by routes, menus, and the UI."""

#: 读自己的工单（列表 / 详情 / 选项）
READ = "support:read"
#: 提交工单与在自己的工单里追加回复
CREATE = "support:create"
#: 客服侧：看全租户工单、改状态/指派、公开与内部回复
MANAGE = "support:manage"

ALL_PERMISSIONS = (READ, CREATE, MANAGE)

__all__ = ["ALL_PERMISSIONS", "CREATE", "MANAGE", "READ"]
