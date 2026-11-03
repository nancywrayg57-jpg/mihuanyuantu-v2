"""
AOJU Backend - Team Schemas

团队管理数据传输对象(DTO)
"""
from pydantic import BaseModel, ConfigDict, Field


class TeamBase(BaseModel):
    """Team base schema"""
    name: str = Field(..., min_length=1, max_length=100, description="团队名称")
    code: str = Field(..., min_length=1, max_length=50, description="团队编码")
    status: int = Field(default=1, ge=0, le=1, description="状态: 0=禁用, 1=启用")
    sort_order: int | None = Field(default=0, description="显示排序")
    description: str | None = Field(default=None, max_length=500, description="团队描述")
    leader: str | None = Field(default=None, max_length=100, description="团队负责人")
    phone: str | None = Field(default=None, max_length=50, description="联系电话")
    email: str | None = Field(default=None, max_length=100, description="邮箱")
    parent_id: int | None = Field(default=None, description="上级团队ID")


class TeamCreate(TeamBase):
    """Team creation schema"""
    pass


class TeamUpdate(BaseModel):
    """
    Team update schema
    
    parent_id 的特殊处理：
    - 不传此字段：不修改上级团队
    - 传 0：设为顶级团队（parent_id = None）
    - 传正整数：移动到指定团队下
    """
    name: str | None = Field(default=None, min_length=1, max_length=100, description="团队名称")
    code: str | None = Field(default=None, min_length=1, max_length=50, description="团队编码")
    status: int | None = Field(default=None, ge=0, le=1, description="状态: 0=禁用, 1=启用")
    sort_order: int | None = Field(default=None, description="显示排序")
    description: str | None = Field(default=None, max_length=500, description="团队描述")
    leader: str | None = Field(default=None, max_length=100, description="团队负责人")
    phone: str | None = Field(default=None, max_length=50, description="联系电话")
    email: str | None = Field(default=None, max_length=100, description="邮箱")
    parent_id: int | None = Field(default=None, ge=0, description="上级团队ID: 0=设为顶级团队, 正整数=移动到指定团队下, 不传=不修改")


class TeamListItem(BaseModel):
    """Team list item schema"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    status: int
    sort_order: int | None
    description: str | None
    leader: str | None
    phone: str | None
    email: str | None
    parent_id: int | None
    tenant_id: int
    created_at: str | None
    updated_at: str | None


class TeamResponse(TeamListItem):
    """Team detail response schema"""
    pass


class TeamTreeNode(TeamListItem):
    """Team tree node schema"""
    children: list["TeamTreeNode"] = Field(default_factory=list, description="子团队列表")


class TeamOption(BaseModel):
    """Team option for select/tree-select"""
    value: int = Field(..., description="团队ID")
    label: str = Field(..., description="团队名称")
    disabled: bool = Field(default=False, description="是否禁用")
    children: list["TeamOption"] = Field(default_factory=list, description="子团队选项")
