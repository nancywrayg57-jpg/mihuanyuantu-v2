"""Foundation module assistant adapters.

These adapters keep base business capabilities out of the default assistant.
The global planner discovers them through execution manifests exactly like
plugin modules do.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.domain.assistant.adapters.base import ActionResult, ModuleAdapterBase
from app.domain.assistant.capability_catalog import build_generic_capability_manifest
from app.domain.assistant.capability_registry import (
    AssistantCapabilityProviderSpec,
    register_assistant_capability_provider,
)
from app.domain.assistant.execution_manifest import infer_action_from_execution_manifest
from app.domain.assistant.schemas import PresetPrompt
from app.domain.assistant.tool_schema import assistant_tool
from app.domain.assistant.toolset_registry import AssistantModuleToolsetSpec, register_assistant_module_toolset
from app.domain.users.models import UserStatus
from app.domain.users.service import UserService

_CREDITS_MY_ACCOUNT_TOOL_ID = "credits.my_account.get"
_USERS_COUNT_TOOL_ID = "users.count"
_USER_READ_PERMISSIONS = {"user:read", "user:list"}


def _is_channel_context(route: str, params: dict[str, Any]) -> bool:
    source = str((params or {}).get("source") or "").strip()
    return source == "message_channel" or str(route or "").strip() == "/message-channel"


def _tool_catalog_item(
    *,
    tool_id: str,
    label: str,
    summary: str,
    resource: str,
    resource_label: str,
    required_permissions: list[str] | None = None,
    examples: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": tool_id,
        "label": label,
        "summary": summary,
        "description": summary,
        "mode": "query",
        "modeLabel": "只读查询",
        "toolType": "query",
        "accessMode": "read",
        "resource": resource,
        "resourceLabel": resource_label,
        "available": True,
        "status": "active",
        "confirmationRequired": False,
        "requiredPermissions": list(required_permissions or []),
        "examples": list(examples or []),
    }


def _role_profile(
    *,
    module_code: str,
    user_id: int,
    tenant_id: int,
    tool_ids: list[str],
) -> dict[str, Any]:
    return {
        "id": f"user:{int(user_id)}",
        "label": "当前登录用户",
        "actorKind": "authenticated_user",
        "moduleCode": module_code,
        "tenantId": int(tenant_id),
        "userId": int(user_id),
        "preferredToolIds": list(tool_ids),
        "availableToolIds": list(tool_ids),
    }


async def _has_any_permission(
    *,
    db,
    tenant_id: int,
    user_id: int,
    permissions: set[str],
) -> bool:
    user_permissions = await UserService(db).get_user_permissions(user_id, tenant_id=tenant_id)
    if "*:*:*" in user_permissions or "*.*.*" in user_permissions:
        return True
    return bool(permissions & user_permissions)


register_assistant_module_toolset(
    AssistantModuleToolsetSpec(
        module_code="credits",
        tool_schemas=(
            assistant_tool(
                _CREDITS_MY_ACCOUNT_TOOL_ID,
                "查询我的积分",
                "读取当前登录用户自己的积分账户余额和账户状态。",
                scope_ids=["credits-personal"],
                examples=["查询下我的积分", "我还有多少积分", "我的积分余额是多少"],
                tool_type="query",
                resource="credits.account",
                access_mode="read",
            ),
        ),
    )
)
register_assistant_capability_provider(
    AssistantCapabilityProviderSpec(
        module_code="credits",
        scope_rules=[("/personal/credits", {"id": "credits-personal", "label": "个人积分"})],
        toolset_module_code="credits",
        role_profiles=[
            {
                "id": "credits-personal",
                "label": "当前登录用户",
                "actorKind": "authenticated_user",
                "preferredToolIds": [_CREDITS_MY_ACCOUNT_TOOL_ID],
            }
        ],
        skill_packs=[
            {
                "id": "credits.personal_query",
                "label": "个人积分查询",
                "description": "查询当前登录用户自己的积分账户。",
                "scopeIds": ["credits-personal"],
                "preferredToolIds": [_CREDITS_MY_ACCOUNT_TOOL_ID],
            }
        ],
        resource_labels={"credits.account": "积分账户"},
    )
)
register_assistant_module_toolset(
    AssistantModuleToolsetSpec(
        module_code="users",
        tool_schemas=(
            assistant_tool(
                _USERS_COUNT_TOOL_ID,
                "统计当前租户用户数",
                "统计当前租户内当前账号可读取范围下的用户数量。",
                scope_ids=["users-admin"],
                required_permissions=sorted(_USER_READ_PERMISSIONS),
                examples=["当前有多少用户", "统计一下用户数量", "现在租户里有几个用户"],
                tool_type="query",
                resource="users",
                access_mode="read",
            ),
        ),
    )
)
register_assistant_capability_provider(
    AssistantCapabilityProviderSpec(
        module_code="users",
        scope_rules=[("/system/user", {"id": "users-admin", "label": "用户管理"})],
        toolset_module_code="users",
        role_profiles=[
            {
                "id": "users-admin",
                "label": "用户管理可读账号",
                "actorKind": "operator",
                "preferredToolIds": [_USERS_COUNT_TOOL_ID],
            }
        ],
        skill_packs=[
            {
                "id": "users.read_summary",
                "label": "用户只读统计",
                "description": "按当前账号权限和数据范围统计用户。",
                "scopeIds": ["users-admin"],
                "preferredToolIds": [_USERS_COUNT_TOOL_ID],
            }
        ],
        resource_labels={"users": "用户管理"},
    )
)


class CreditsAssistantAdapter(ModuleAdapterBase):
    """Assistant adapter for user credit account queries."""

    module_code = "credits"
    module_name = "积分"
    supported_routes = ["/personal/credits", "/system/credits", "/system/credits*"]
    default_chat_prompt = "围绕积分账户和积分流水回答；可用只读工具能查询真实积分数据时，不要只给导航建议。"

    def get_execution_manifest(self) -> dict[str, Any]:
        return super().get_execution_manifest()

    async def get_context(
        self,
        route: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        del db, viewer_team_ids, read_team_ids
        return {
            "today": date.today().isoformat(),
            "route": route,
            "params": params,
            "source": "message_channel" if _is_channel_context(route, params) else "web",
            "pageContextAvailable": not _is_channel_context(route, params),
            "businessModule": self.module_code,
            "currentRoleProfile": _role_profile(
                module_code=self.module_code,
                user_id=user_id,
                tenant_id=tenant_id,
                tool_ids=[_CREDITS_MY_ACCOUNT_TOOL_ID],
            ),
            "message": "积分模块上下文。可以查询当前登录用户自己的积分账户。",
        }

    async def get_presets(
        self,
        route: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> list[PresetPrompt]:
        del route, params, db, tenant_id, user_id, viewer_team_ids, read_team_ids
        return [
            PresetPrompt(id="credits-my-balance", label="我的积分", prompt="查询下我的积分", icon="coins"),
            PresetPrompt(id="credits-help", label="积分能力", prompt="这个积分 Channel 能查询什么？", icon="question"),
        ]

    async def get_capability_source(
        self,
        route: str,
        params: dict[str, Any],
        *,
        context_data: dict[str, Any] | None,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> dict[str, Any] | None:
        del route, params, context_data, db, viewer_team_ids, read_team_ids
        tool_catalog = [
            _tool_catalog_item(
                tool_id=_CREDITS_MY_ACCOUNT_TOOL_ID,
                label="查询我的积分",
                summary="读取当前登录用户自己的积分账户余额和账户状态。",
                resource="credits.account",
                resource_label="积分账户",
                examples=["查询下我的积分", "我还有多少积分"],
            )
        ]
        role_profile = _role_profile(
            module_code=self.module_code,
            user_id=user_id,
            tenant_id=tenant_id,
            tool_ids=[_CREDITS_MY_ACCOUNT_TOOL_ID],
        )
        skill_packs = [
            {
                "id": "credits.personal_query",
                "label": "个人积分查询",
                "description": "查询当前登录用户自己的积分账户。",
                "available": True,
                "availableToolIds": [_CREDITS_MY_ACCOUNT_TOOL_ID],
                "preferredToolIds": [_CREDITS_MY_ACCOUNT_TOOL_ID],
            }
        ]
        return {
            "currentRoleProfile": role_profile,
            "toolCatalog": tool_catalog,
            "skillPacks": skill_packs,
            "capabilityManifest": build_generic_capability_manifest(
                scope_id=self.module_code,
                role_profile=role_profile,
                tool_catalog=tool_catalog,
                skill_packs=skill_packs,
            ),
            "operationPolicy": {
                "auth": "Use only the bound current user.",
                "readScope": "Personal credit queries may read only the current user's own account.",
                "writeGuard": "No credit mutation is exposed by this adapter.",
            },
        }

    def get_governance_skill_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "credits.personal_query",
                "label": "个人积分查询",
                "description": "查询当前登录用户自己的积分账户。",
            }
        ]

    async def infer_action_from_reply(
        self,
        reply: str,
        route: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
        prior_action: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        del params, db, tenant_id, user_id, viewer_team_ids, read_team_ids, prior_action
        return infer_action_from_execution_manifest(
            manifest=self.get_execution_manifest(),
            text=reply,
            active_module_code=self.module_code,
            current_route_path=route,
            threshold=80,
        )

    async def execute_action(
        self,
        action: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> ActionResult:
        del params, viewer_team_ids, read_team_ids
        if action != _CREDITS_MY_ACCOUNT_TOOL_ID:
            return ActionResult(success=False, message="积分模块不支持此操作。")

        from app.domain.credits.service import CreditService

        service = CreditService(db)
        account = await service.get_user_account(tenant_id=tenant_id, user_id=user_id)
        if not account:
            account = await service.init_user_account(tenant_id=tenant_id, user_id=user_id, operator_id=user_id)
        payload = CreditService.to_account_response(account)
        balance = str(payload.get("balance") or "0")
        total_earned = str(payload.get("totalEarned") or "0")
        total_spent = str(payload.get("totalSpent") or "0")
        status = str(payload.get("status") or "").strip() or "active"
        return ActionResult(
            success=True,
            data={
                "account": payload,
                "queryContext": {
                    "toolId": _CREDITS_MY_ACCOUNT_TOOL_ID,
                    "success": True,
                    "emptyResult": False,
                    "returnedCount": 1,
                },
            },
            message=f"你的当前积分余额为 {balance}，累计获得 {total_earned}，累计消费 {total_spent}，账户状态为 {status}。",
        )


class UsersAssistantAdapter(ModuleAdapterBase):
    """Assistant adapter for user-management read queries."""

    module_code = "users"
    module_name = "用户管理"
    supported_routes = ["/system/user", "/system/user*"]
    default_chat_prompt = "围绕用户管理回答；只有在权限允许时才读取用户列表、统计和审核数据。"

    def get_execution_manifest(self) -> dict[str, Any]:
        return super().get_execution_manifest()

    async def get_context(
        self,
        route: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        del db, viewer_team_ids
        return {
            "today": date.today().isoformat(),
            "route": route,
            "params": params,
            "source": "message_channel" if _is_channel_context(route, params) else "web",
            "pageContextAvailable": not _is_channel_context(route, params),
            "businessModule": self.module_code,
            "dataScope": {
                "readTeamIds": [] if read_team_ids is None else list(read_team_ids),
                "hasAllReadAccess": read_team_ids is None,
            },
            "currentRoleProfile": _role_profile(
                module_code=self.module_code,
                user_id=user_id,
                tenant_id=tenant_id,
                tool_ids=[_USERS_COUNT_TOOL_ID],
            ),
            "message": "用户管理模块上下文。用户统计必须通过权限和数据范围校验。",
        }

    async def get_presets(
        self,
        route: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> list[PresetPrompt]:
        del route, params, db, tenant_id, user_id, viewer_team_ids, read_team_ids
        return [
            PresetPrompt(id="users-count", label="用户数量", prompt="当前有多少用户", icon="users"),
            PresetPrompt(id="users-help", label="用户能力", prompt="用户管理现在能查询什么？", icon="question"),
        ]

    async def get_capability_source(
        self,
        route: str,
        params: dict[str, Any],
        *,
        context_data: dict[str, Any] | None,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> dict[str, Any] | None:
        del route, params, context_data, db, viewer_team_ids, read_team_ids
        tool_catalog = [
            _tool_catalog_item(
                tool_id=_USERS_COUNT_TOOL_ID,
                label="统计当前租户用户数",
                summary="统计当前租户内当前账号可读取范围下的用户数量。",
                resource="users",
                resource_label="用户管理",
                required_permissions=sorted(_USER_READ_PERMISSIONS),
                examples=["当前有多少用户", "统计一下用户数量"],
            )
        ]
        role_profile = _role_profile(
            module_code=self.module_code,
            user_id=user_id,
            tenant_id=tenant_id,
            tool_ids=[_USERS_COUNT_TOOL_ID],
        )
        skill_packs = [
            {
                "id": "users.read_summary",
                "label": "用户只读统计",
                "description": "按当前账号权限和数据范围统计用户。",
                "available": True,
                "availableToolIds": [_USERS_COUNT_TOOL_ID],
                "preferredToolIds": [_USERS_COUNT_TOOL_ID],
            }
        ]
        return {
            "currentRoleProfile": role_profile,
            "toolCatalog": tool_catalog,
            "skillPacks": skill_packs,
            "capabilityManifest": build_generic_capability_manifest(
                scope_id=self.module_code,
                role_profile=role_profile,
                tool_catalog=tool_catalog,
                skill_packs=skill_packs,
            ),
            "operationPolicy": {
                "auth": "Require user:read or user:list, or superuser wildcard permission.",
                "readScope": "Apply read_team_ids data scope when present.",
                "writeGuard": "No user mutation is exposed by this adapter.",
            },
        }

    def get_governance_skill_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "users.read_summary",
                "label": "用户只读统计",
                "description": "按当前账号权限和数据范围统计用户。",
            }
        ]

    async def infer_action_from_reply(
        self,
        reply: str,
        route: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
        prior_action: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        del params, db, tenant_id, user_id, viewer_team_ids, read_team_ids, prior_action
        return infer_action_from_execution_manifest(
            manifest=self.get_execution_manifest(),
            text=reply,
            active_module_code=self.module_code,
            current_route_path=route,
            threshold=80,
        )

    async def execute_action(
        self,
        action: str,
        params: dict[str, Any],
        *,
        db,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None = None,
    ) -> ActionResult:
        del params, viewer_team_ids
        if action != _USERS_COUNT_TOOL_ID:
            return ActionResult(success=False, message="用户管理模块不支持此操作。")
        if not await _has_any_permission(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            permissions=_USER_READ_PERMISSIONS,
        ):
            return ActionResult(
                success=False,
                data={
                    "permissionDenied": True,
                    "queryContext": {
                        "toolId": _USERS_COUNT_TOOL_ID,
                        "success": False,
                        "emptyResult": True,
                    },
                },
                message="当前账号没有查看用户统计的权限。需要 user:read 或 user:list 权限。",
            )
        if read_team_ids == []:
            payload = {
                "tenantId": int(tenant_id),
                "totalUsers": 0,
                "enabledUsers": 0,
                "disabledUsers": 0,
                "pendingUsers": 0,
                "rejectedUsers": 0,
            }
        else:
            service = UserService(db)
            _users, total = await service.list_users(tenant_id=tenant_id, page=1, page_size=1, team_ids=read_team_ids)
            _enabled_users, enabled = await service.list_users(
                tenant_id=tenant_id,
                page=1,
                page_size=1,
                status=int(UserStatus.ENABLED),
                team_ids=read_team_ids,
            )
            _disabled_users, disabled = await service.list_users(
                tenant_id=tenant_id,
                page=1,
                page_size=1,
                status=int(UserStatus.DISABLED),
                team_ids=read_team_ids,
            )
            _pending_users, pending = await service.list_users(
                tenant_id=tenant_id,
                page=1,
                page_size=1,
                status=int(UserStatus.PENDING),
                team_ids=read_team_ids,
            )
            _rejected_users, rejected = await service.list_users(
                tenant_id=tenant_id,
                page=1,
                page_size=1,
                status=int(UserStatus.REJECTED),
                team_ids=read_team_ids,
            )
            payload = {
                "tenantId": int(tenant_id),
                "totalUsers": int(total or 0),
                "enabledUsers": int(enabled or 0),
                "disabledUsers": int(disabled or 0),
                "pendingUsers": int(pending or 0),
                "rejectedUsers": int(rejected or 0),
            }
        return ActionResult(
            success=True,
            data={
                "stats": payload,
                "queryContext": {
                    "toolId": _USERS_COUNT_TOOL_ID,
                    "success": True,
                    "emptyResult": payload["totalUsers"] == 0,
                    "returnedCount": 1,
                },
            },
            message=(
                f"当前可读取范围内共有 {payload['totalUsers']} 个用户，其中正常 {payload['enabledUsers']} 个，"
                f"禁用 {payload['disabledUsers']} 个，待审核 {payload['pendingUsers']} 个，"
                f"已拒绝 {payload['rejectedUsers']} 个。"
            ),
        )
