"""
AOJU Backend - Base Repository

通用数据访问层基类，提供常用的 CRUD 操作。

使用方式：
    class UserRepository(RepositoryBase[User]):
        def __init__(self, db: AsyncSession):
            super().__init__(db, User)
"""
from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar, Union

from sqlalchemy import BinaryExpression, ScalarResult, Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.strategy_options import _AbstractLoad

from app.core.exceptions import NotFoundError

# 泛型类型变量，用于指定模型类型
ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class RepositoryBase(Generic[ModelType]):
    """
    通用 Repository 基类
    
    提供常用的数据库操作方法：
    - get_by_id: 根据 ID 获取单条数据
    - get_one: 根据条件获取单条数据
    - get_list: 获取数据列表（支持分页）
    - get_count: 获取数据总数
    - create: 创建单条数据
    - create_batch: 批量创建数据
    - update: 更新数据
    - delete: 删除数据（软删除）
    - delete_permanently: 永久删除数据
    
    注意：
    - 所有查询方法默认过滤软删除的数据（deleted_at IS NULL）
    - 如果模型没有 deleted_at 字段，则不会添加软删除过滤
    """
    
    # 排序字段
    ORDER_DESC = ["desc", "descending"]
    
    def __init__(self, db: AsyncSession, model: type[ModelType]):
        """
        初始化 Repository
        
        Args:
            db: 数据库会话
            model: ORM 模型类
        """
        self.db = db
        self.model = model
        # 检查模型是否支持软删除
        self._has_soft_delete = hasattr(model, "deleted_at")
    
    def _add_soft_delete_filter(self, stmt: Select) -> Select:
        """
        添加软删除过滤条件
        
        Args:
            stmt: SQLAlchemy Select 语句
            
        Returns:
            添加了软删除过滤的 Select 语句
        """
        if self._has_soft_delete:
            return stmt.where(self.model.deleted_at.is_(None))
        return stmt
    
    async def get_by_id(
        self,
        id: int,
        *,
        options: Optional[list[_AbstractLoad]] = None,
        raise_not_found: bool = True,
        include_deleted: bool = False,
    ) -> Optional[ModelType]:
        """
        根据 ID 获取单条数据
        
        Args:
            id: 数据 ID
            options: SQLAlchemy 加载选项（如 selectinload, joinedload）
            raise_not_found: 未找到时是否抛出异常
            include_deleted: 是否包含已软删除的数据
            
        Returns:
            模型实例或 None
            
        Raises:
            NotFoundError: 当 raise_not_found=True 且未找到数据时
        """
        stmt = select(self.model).where(self.model.id == id)
        
        if not include_deleted:
            stmt = self._add_soft_delete_filter(stmt)
        
        if options:
            stmt = stmt.options(*options)
        
        result = await self.db.execute(stmt)
        data = result.scalar_one_or_none()
        
        if not data and raise_not_found:
            raise NotFoundError(message=f"{self.model.__name__} not found")
        
        return data
    
    async def get_one(
        self,
        *,
        where: Optional[list[BinaryExpression]] = None,
        options: Optional[list[_AbstractLoad]] = None,
        raise_not_found: bool = False,
        include_deleted: bool = False,
        **filters,
    ) -> Optional[ModelType]:
        """
        根据条件获取单条数据
        
        Args:
            where: 原始 WHERE 条件列表
            options: SQLAlchemy 加载选项
            raise_not_found: 未找到时是否抛出异常
            include_deleted: 是否包含已软删除的数据
            **filters: 字段过滤条件（支持简单相等查询）
            
        Returns:
            模型实例或 None
            
        Example:
            # 简单查询
            user = await repo.get_one(username="admin")
            
            # 复杂查询
            user = await repo.get_one(
                where=[User.status == 1, User.tenant_id == 1],
                options=[selectinload(User.roles)]
            )
        """
        stmt = select(self.model)
        
        if not include_deleted:
            stmt = self._add_soft_delete_filter(stmt)
        
        if where:
            stmt = stmt.where(*where)
        
        if filters:
            conditions = self._build_filter_conditions(**filters)
            if conditions:
                stmt = stmt.where(*conditions)
        
        if options:
            stmt = stmt.options(*options)
        
        result = await self.db.execute(stmt)
        data = result.scalar_one_or_none()
        
        if not data and raise_not_found:
            raise NotFoundError(message=f"{self.model.__name__} not found")
        
        return data
    
    async def get_list(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        where: Optional[list[BinaryExpression]] = None,
        options: Optional[list[_AbstractLoad]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        return_total: bool = False,
        include_deleted: bool = False,
        **filters,
    ) -> Union[list[ModelType], tuple[list[ModelType], int]]:
        """
        获取数据列表（支持分页）
        
        Args:
            page: 页码（从 1 开始）
            page_size: 每页数量（0 表示不分页）
            where: 原始 WHERE 条件列表
            options: SQLAlchemy 加载选项
            order_by: 排序字段名
            order_desc: 是否倒序
            return_total: 是否返回总数
            include_deleted: 是否包含已软删除的数据
            **filters: 字段过滤条件
            
        Returns:
            数据列表，或 (数据列表, 总数) 元组
            
        Example:
            # 分页查询
            users, total = await repo.get_list(
                page=1,
                page_size=10,
                status=1,
                return_total=True
            )
            
            # 不分页查询
            all_users = await repo.get_list(page_size=0, status=1)
        """
        stmt = select(self.model)
        
        if not include_deleted:
            stmt = self._add_soft_delete_filter(stmt)
        
        if where:
            stmt = stmt.where(*where)
        
        if filters:
            conditions = self._build_filter_conditions(**filters)
            if conditions:
                stmt = stmt.where(*conditions)
        
        if options:
            stmt = stmt.options(*options)
        
        # 排序
        if order_by:
            order_field = getattr(self.model, order_by)
            if order_desc:
                stmt = stmt.order_by(order_field.desc(), self.model.id.desc())
            else:
                stmt = stmt.order_by(order_field, self.model.id)
        elif order_desc:
            stmt = stmt.order_by(self.model.id.desc())
        else:
            stmt = stmt.order_by(self.model.id)
        
        # 获取总数
        total = 0
        if return_total:
            count_stmt = select(func.count()).select_from(stmt.alias())
            count_result = await self.db.execute(count_stmt)
            total = count_result.scalar() or 0
        
        # 分页
        if page_size > 0:
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(stmt)
        
        if options:
            data = list(result.scalars().unique().all())
        else:
            data = list(result.scalars().all())
        
        if return_total:
            return data, total
        return data
    
    async def get_count(
        self,
        *,
        where: Optional[list[BinaryExpression]] = None,
        include_deleted: bool = False,
        **filters,
    ) -> int:
        """
        获取数据总数
        
        Args:
            where: 原始 WHERE 条件列表
            include_deleted: 是否包含已软删除的数据
            **filters: 字段过滤条件
            
        Returns:
            数据总数
        """
        stmt = select(func.count(self.model.id))
        
        if not include_deleted:
            stmt = self._add_soft_delete_filter(stmt)
        
        if where:
            stmt = stmt.where(*where)
        
        if filters:
            conditions = self._build_filter_conditions(**filters)
            if conditions:
                stmt = stmt.where(*conditions)
        
        result = await self.db.execute(stmt)
        return result.scalar() or 0
    
    async def create(self, data: Union[dict, Any]) -> ModelType:
        """
        创建单条数据
        
        Args:
            data: 字典或 Pydantic 模型
            
        Returns:
            创建的模型实例
            
        Example:
            user = await repo.create({"username": "admin", "email": "admin@example.com"})
            # 或
            user = await repo.create(UserCreate(username="admin", email="admin@example.com"))
        """
        if isinstance(data, dict):
            obj = self.model(**data)
        else:
            obj = self.model(**data.model_dump())
        
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj
    
    async def create_batch(self, data_list: list[dict]) -> None:
        """
        批量创建数据
        
        Args:
            data_list: 字典列表
            
        Note:
            批量插入不返回创建的对象
        """
        if not data_list:
            return
        
        objs = [self.model(**data) for data in data_list]
        self.db.add_all(objs)
        await self.db.flush()
    
    async def update(
        self,
        obj: ModelType,
        data: Union[dict, Any],
        *,
        exclude_unset: bool = True,
        exclude_none: bool = False,
    ) -> ModelType:
        """
        更新数据
        
        Args:
            obj: 要更新的模型实例
            data: 更新数据（字典或 Pydantic 模型）
            exclude_unset: 排除未设置的字段
            exclude_none: 排除 None 值字段
            
        Returns:
            更新后的模型实例
            
        Example:
            user = await repo.get_by_id(1)
            updated_user = await repo.update(user, {"email": "new@example.com"})
        """
        if isinstance(data, dict):
            update_data = data
        else:
            update_data = data.model_dump(
                exclude_unset=exclude_unset,
                exclude_none=exclude_none,
            )
        
        for field, value in update_data.items():
            if hasattr(obj, field):
                setattr(obj, field, value)
        
        await self.db.flush()
        await self.db.refresh(obj)
        return obj
    
    async def delete(self, obj: ModelType) -> None:
        """
        软删除数据
        
        Args:
            obj: 要删除的模型实例
            
        Note:
            如果模型不支持软删除（没有 deleted_at 字段），则执行物理删除
        """
        if self._has_soft_delete:
            obj.deleted_at = datetime.now(timezone.utc)
            await self.db.flush()
        else:
            await self.delete_permanently(obj)
    
    async def delete_by_id(self, id: int) -> None:
        """
        根据 ID 软删除数据
        
        Args:
            id: 数据 ID
        """
        obj = await self.get_by_id(id)
        await self.delete(obj)
    
    async def delete_batch(self, ids: list[int]) -> None:
        """
        批量软删除数据
        
        Args:
            ids: ID 列表
            
        Note:
            如果模型不支持软删除（没有 deleted_at 字段），则执行物理删除
        """
        if not ids:
            return
        
        if self._has_soft_delete:
            await self.db.execute(
                update(self.model)
                .where(self.model.id.in_(ids))
                .values(deleted_at=datetime.now(timezone.utc))
            )
        else:
            await self.db.execute(
                delete(self.model).where(self.model.id.in_(ids))
            )
        await self.db.flush()
    
    async def delete_permanently(self, obj: ModelType) -> None:
        """
        永久删除数据（物理删除）
        
        Args:
            obj: 要删除的模型实例
            
        Warning:
            此操作不可恢复，请谨慎使用
        """
        await self.db.delete(obj)
        await self.db.flush()
    
    async def delete_permanently_by_id(self, id: int) -> None:
        """
        根据 ID 永久删除数据
        
        Args:
            id: 数据 ID
        """
        await self.db.execute(delete(self.model).where(self.model.id == id))
        await self.db.flush()
    
    def _build_filter_conditions(self, **filters) -> list[BinaryExpression]:
        """
        构建过滤条件
        
        支持的过滤语法：
        - 简单相等: field=value
        - LIKE 查询: field=("like", value)
        - IN 查询: field=("in", [value1, value2])
        - 范围查询: field=("between", [start, end])
        - 不等于: field=("!=", value)
        - 大于: field=(">", value)
        - 大于等于: field=(">=", value)
        - 小于等于: field=("<=", value)
        - IS NULL: field=("is", None)
        - IS NOT NULL: field=("is_not", None)
        
        Args:
            **filters: 过滤条件
            
        Returns:
            条件表达式列表
        """
        conditions = []
        
        for field, value in filters.items():
            if value is None or value == "":
                continue
            
            if not hasattr(self.model, field):
                continue
            
            attr = getattr(self.model, field)
            
            # 元组表示复杂查询
            if isinstance(value, tuple):
                if len(value) == 2:
                    operator, val = value
                    
                    if operator == "like" and val:
                        conditions.append(attr.like(f"%{val}%"))
                    elif operator == "in" and val:
                        conditions.append(attr.in_(val))
                    elif operator == "between" and isinstance(val, (list, tuple)) and len(val) == 2:
                        conditions.append(attr.between(val[0], val[1]))
                    elif operator == "!=":
                        conditions.append(attr != val)
                    elif operator == ">":
                        conditions.append(attr > val)
                    elif operator == ">=":
                        conditions.append(attr >= val)
                    elif operator == "<=":
                        conditions.append(attr <= val)
                    elif operator == "<":
                        conditions.append(attr < val)
                    elif operator == "is" and val is None:
                        conditions.append(attr.is_(None))
                    elif operator == "is_not" and val is None:
                        conditions.append(attr.isnot(None))
            else:
                # 简单相等查询
                conditions.append(attr == value)
        
        return conditions
