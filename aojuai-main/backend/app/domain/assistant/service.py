"""
AOJU Backend - AI Assistant Service
"""
from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import re
from collections.abc import AsyncGenerator
from datetime import UTC
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logger import get_logger
from app.domain.assistant.action_protocol import (
    build_action_execution_history_suffix,
    build_action_history_suffix,
    extract_assistant_action,
    normalize_assistant_action,
    sanitize_streaming_assistant_text,
    summarize_action_execution,
)
from app.domain.assistant.adapters import ActionResult, AdapterRegistry
from app.domain.assistant.billing import (
    build_billing_policy,
    build_billing_result_payload,
    build_prompt_text_from_messages,
    charge_credits_by_usage,
    ensure_credit_precheck,
)
from app.domain.assistant.capability_runtime import (
    assistant_builtin_tool_catalog,
    build_assistant_capability_context,
    build_assistant_capability_context_text,
    execute_assistant_builtin_tool,
)
from app.domain.assistant.execution_planner import AssistantExecutionPlan, AssistantExecutionPlanner
from app.domain.assistant.models import AssistantMessage, AssistantSession, MessageRole
from app.domain.assistant.module_skill_governance import (
    apply_module_skill_governance_to_action,
    apply_module_skill_governance_to_context,
)
from app.domain.assistant.prompt_context import build_generic_prompt_context, compact_prompt_value
from app.domain.assistant.router_service import is_text_entry_route, routing_state_key
from app.domain.assistant.schemas import (
    ActionResponse,
    ChatReplyResponse,
    ContextResponse,
    MessageResponse,
    PresetsResponse,
    SessionResponse,
)
from app.domain.credits.service import CreditService
from app.domain.credits.usage import collects_usage
from app.domain.users.models import UserTeam

logger = get_logger(__name__)
_ASSISTANT_AI_RETRY_DELAYS = (0.0, 0.4)
_ASSISTANT_INTERNAL_PARAM_PREFIX = "_assistant"
_ASSISTANT_LAST_ACTION_EXECUTION_KEY = f"{_ASSISTANT_INTERNAL_PARAM_PREFIX}LastActionExecution"
_ASSISTANT_MEMORY_KEY = f"{_ASSISTANT_INTERNAL_PARAM_PREFIX}Memory"
_ASSISTANT_ENTRY_KEY = f"{_ASSISTANT_INTERNAL_PARAM_PREFIX}Entry"
_ASSISTANT_PLANNER_BILLING_KEY = f"{_ASSISTANT_INTERNAL_PARAM_PREFIX}PlannerBilling"
_ASSISTANT_HISTORY_FETCH_LIMIT = 48
_ASSISTANT_RECENT_HISTORY_LIMIT = 16
_ASSISTANT_HISTORY_MESSAGE_CHAR_LIMIT = 1400
_ASSISTANT_MEMORY_TEXT_LIMIT = 1400
_ASSISTANT_MEMORY_TURN_LIMIT = 8
_MESSAGE_CHANNEL_ROUTE = "/message-channel"
_ASSISTANT_FOLLOWUP_MARKERS = (
    "继续",
    "下一",
    "上一",
    "更多",
    "还有",
    "再来",
    "再查",
    "详细",
    "详情",
    "明细",
    "这个",
    "那个",
    "这些",
    "刚才",
    "前面",
    "结果",
    "状态",
    "为什么",
    "怎么办",
    "可以吗",
    "呢",
    "吗",
)
_ASSISTANT_NEW_TASK_MARKERS = (
    "安排",
    "创建",
    "新增",
    "修改",
    "删除",
    "审核",
    "配置",
    "绑定",
    "生成",
    "打开",
    "进入",
    "前往",
    "跳转",
    "导航",
)


def _normalize_route_path(value: str | None) -> str:
    route = str(value or "").strip()
    if not route:
        return "/"
    if not route.startswith("/"):
        return f"/{route}"
    return route


def _trim_prompt_text(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 1)].rstrip()}…"


def _tail_trim_prompt_text(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"…{text[-max(0, limit - 1):].lstrip()}"


class AssistantService:
    """AI助手服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.credit_service = CreditService(db)

    @staticmethod
    def _build_system_prompt(
        *,
        system_prompt: str,
        module_prompt: str,
        write_guard_prompt: str,
        module_name: str,
        route_path: str,
        prompt_context: dict[str, Any] | None = None,
        context_data: dict[str, Any] | None = None,
        capability_context_text: str = "",
        prior_action: dict[str, Any] | None = None,
        prior_execution: dict[str, Any] | None = None,
    ) -> str:
        resolved_prompt_context = (
            prompt_context if isinstance(prompt_context, dict) else context_data if isinstance(context_data, dict) else {}
        )
        prompt_context_text = json.dumps(resolved_prompt_context, ensure_ascii=False)
        capability_block = (
            f"【能力框架】\n{capability_context_text}\n\n"
            if str(capability_context_text or "").strip()
            else ""
        )
        prior_action_block = ""
        compact_prior_action = AssistantService._summarize_prior_action_for_prompt(prior_action)
        if compact_prior_action is not None:
            prior_action_block = (
                "【上一轮动作摘要】如当前问题是在延续上一轮查询或操作，请优先参考这里的结构化状态。\n"
                f"{json.dumps(compact_prior_action, ensure_ascii=False)}\n\n"
            )
        prior_execution_block = ""
        compact_prior_execution = AssistantService._extract_prior_execution_summary(prior_action)
        if compact_prior_execution is None and isinstance(prior_execution, dict):
            compact_prior_execution = compact_prompt_value(prior_execution, max_items=12)
        if compact_prior_execution is not None:
            prior_execution_block = (
                "【上一轮真实执行摘要】如果这是继续翻页、补充筛选、重新搜索或追问结果，请优先参考这里的 queryContext。\n"
                f"{json.dumps(compact_prior_execution, ensure_ascii=False)}\n\n"
            )
        assistant_entry = (
            resolved_prompt_context.get("assistantEntry")
            if isinstance(resolved_prompt_context.get("assistantEntry"), dict)
            else {}
        )
        is_message_channel = (
            isinstance(assistant_entry, dict)
            and (
                assistant_entry.get("isMessageChannel") is True
                or str(assistant_entry.get("source") or "").strip() == "message_channel"
            )
        )
        route_label = "【执行范围】" if is_message_channel else "【当前路由】"
        channel_block = ""
        if is_message_channel:
            channel_block = (
                "【Channel 交互约束】当前入口是微信/飞书等消息 Channel，不存在浏览器当前页、按钮、侧栏或跳转卡片。"
                "routePath 只代表本轮内部执行范围，不代表用户正在浏览该页面。"
                "不要输出“点击按钮”“前往页面”“打开右侧卡片”“可前往”等网页 UI 措辞；"
                "如果 read/query Tool 可以执行，直接返回执行结果；如果只能在网页端完成，请用一句话说明需要到 AOJUAI 网页端对应模块处理。"
                "Channel 回复必须是纯文本或简洁 Markdown，不要暴露 assistantAction、toolId 或内部协议。\n"
            )
        return (
            f"{system_prompt}\n\n"
            f"【当前模块】{module_name}\n"
            f"{route_label}{route_path}\n"
            f"{capability_block}"
            f"{prior_action_block}"
            f"{prior_execution_block}"
            f"【当前页面契约】{prompt_context_text}\n\n"
            f"【模块策略】{module_prompt}\n"
            f"【写入守卫】{write_guard_prompt}\n"
            f"{channel_block}"
            "【身份与权限】当前身份以能力框架 sessionScope 和页面契约 currentRoleProfile/systemIdentity/dataScope 为准；"
            "不要把已登录用户称为访客。所有回答和动作必须遵守绑定用户的租户、角色、团队数据范围。\n"
            "【空白上下文约束】如果页面契约显示 pageContextAvailable=false 或 source=message_channel，"
            "表示当前没有打开业务页面、没有具体业务对象上下文；不要臆造项目、日程、任务、客户、表单等内容，"
            "除非用户在消息中明确提供这些业务对象。\n"
            "【动作约束】只有当前页面契约中 toolCatalog 的 toolId，才允许作为 assistantAction 输出。\n"
            "如果当前页面契约里提供了 scopeDirectory，请先判断 currentScope 是否足够回答；"
            "若不足，再查看 moduleScope；只有当前页面和当前模块都不足时，才扩展到 globalScope。"
            "如需跨页面处理且 toolCatalog 允许 page.router.navigate，请输出结构化导航动作，"
            "并在动作里显式补充 targetRoutePath / targetModuleCode；正文只保留一句简短说明。"
            "不要把 assistantAction JSON、toolId、targetRoutePath 或内部协议原文展示给用户。\n"
            "【长对话约束】assistantMemory 和压缩会话记忆只用于保留长期偏好、已确认约束和最近模块切换，"
            "不能把旧模块、旧页面或旧查询结果当作当前模块事实。用户明显切换业务对象或模块时，"
            "以本轮消息、当前路由、当前页面契约和当前 toolCatalog 为准；必要时先澄清，不要跨模块臆造数据。\n"
            "【能力边界】你不是通用闲聊或公网问答助手。只处理 AOJUAI 平台内当前页面、已注册模块、已发布 Tool。"
            "若问题没有匹配到已注册能力，不要凭常识回答，也不要假装能调用外部服务；"
            "请说明当前没有可用能力，并提示需要管理员接入相应 Tool 或让用户说明要处理的系统模块。\n"
            "先回答可执行建议。若涉及写入动作，先给出待确认方案。"
            "如果上一轮真实执行摘要里已经给出 queryContext.totalCount、returnedCount、remainingCount 或 emptyResult，"
            "请直接基于这些事实判断是否还有后续结果、是否需要改筛选、是否应该重试。"
            "如果当前用户话语结合上下文仍然存在多个合理解释，例如既可能表示继续翻页，也可能表示改条件重搜，"
            "就不要猜测，不要擅自扩大查询范围；此时请直接提出一句简短澄清问题，并且不要输出 assistantAction。"
        ).strip()

    @staticmethod
    def _build_fallback_reply(module_name: str, presets: list[str]) -> str:
        if not presets:
            return f"{module_name}暂时无法连接 AI 服务，请稍后重试。"
        tips = "；".join(presets[:2])
        return f"{module_name}当前进入本地降级模式。你可以先尝试：{tips}"

    @staticmethod
    def _normalize_role(role: str) -> str | None:
        value = str(role or "").strip().lower()
        if value in {"user", "assistant", "system"}:
            return value
        return None

    def _resolve_adapter(self, route_path: str):
        adapter = AdapterRegistry.resolve_by_route(route_path)
        if adapter:
            return adapter
        fallback = AdapterRegistry.get("default")
        if fallback:
            return fallback
        raise RuntimeError("Assistant default adapter not registered")

    @staticmethod
    def _derive_team_ids(team_ids: list[int] | None) -> list[int] | None:
        if team_ids is None:
            return None
        if not team_ids:
            return []
        normalized = []
        for item in team_ids:
            if isinstance(item, int):
                normalized.append(item)
        return normalized

    @staticmethod
    def _is_message_channel_context(route_path: str | None, context_params: dict[str, Any] | None) -> bool:
        route = _normalize_route_path(route_path)
        source = str((context_params or {}).get("source") or "").strip()
        return source == "message_channel" or route == _MESSAGE_CHANNEL_ROUTE

    @staticmethod
    def _merge_internal_session_context(
        context_params: dict[str, Any] | None,
        session_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = dict(context_params or {}) if isinstance(context_params, dict) else {}
        if not isinstance(session_context, dict):
            return merged
        for key, value in session_context.items():
            normalized_key = str(key or "").strip()
            if not normalized_key.startswith(_ASSISTANT_INTERNAL_PARAM_PREFIX):
                continue
            if normalized_key == _ASSISTANT_PLANNER_BILLING_KEY:
                continue
            if normalized_key not in merged:
                merged[normalized_key] = value
        return merged

    @staticmethod
    def _extract_context_routing_state(*sources: dict[str, Any] | None) -> dict[str, Any] | None:
        key = routing_state_key()
        for source in sources:
            if not isinstance(source, dict):
                continue
            routing = source.get(key)
            if isinstance(routing, dict) and routing:
                return dict(routing)
        return None

    @staticmethod
    def _routing_used_ai(context_params: dict[str, Any] | None) -> bool:
        if not isinstance(context_params, dict):
            return False
        routing = context_params.get(routing_state_key())
        if isinstance(routing, dict) and str(routing.get("source") or "").strip() == "ai_planner":
            return True
        planner_billing = context_params.get(_ASSISTANT_PLANNER_BILLING_KEY)
        if not isinstance(planner_billing, dict):
            return False
        return int(planner_billing.get("providerCalls") or 0) > 0 or int(planner_billing.get("totalTokens") or 0) > 0

    @staticmethod
    def _build_billing_policy_from_config(assistant_config: Any):
        config_payload = assistant_config.config if assistant_config and isinstance(getattr(assistant_config, "config", None), dict) else {}
        return build_billing_policy(
            deduct_credits=bool(assistant_config and assistant_config.deduct_credits),
            points_token_ratio=config_payload.get("points_token_ratio", 1000),
            credits_per_call=(assistant_config.credits_per_call if assistant_config else 1),
        )

    @staticmethod
    def _planner_billing_payload(context_params: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(context_params, dict):
            return None
        payload = context_params.get(_ASSISTANT_PLANNER_BILLING_KEY)
        return dict(payload) if isinstance(payload, dict) and payload else None

    @staticmethod
    def _merge_billing_payloads(*items: dict[str, Any] | None) -> dict[str, Any] | None:
        normalized_items = [dict(item) for item in items if isinstance(item, dict) and item]
        if not normalized_items:
            return None
        amount = Decimal("0")
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        provider_calls = 0
        transaction_ids: list[int] = []
        enabled = False
        charged = False
        for item in normalized_items:
            enabled = enabled or bool(item.get("enabled"))
            charged = charged or bool(item.get("charged"))
            with contextlib.suppress(InvalidOperation, TypeError, ValueError):
                amount += Decimal(str(item.get("amount") or "0"))
            input_tokens += int(item.get("inputTokens") or 0)
            output_tokens += int(item.get("outputTokens") or 0)
            total_tokens += int(item.get("totalTokens") or 0)
            provider_calls += int(item.get("providerCalls") or 0)
            try:
                normalized_tx_id = int(item.get("transactionId") or 0)
            except Exception:
                normalized_tx_id = 0
            if normalized_tx_id > 0 and normalized_tx_id not in transaction_ids:
                transaction_ids.append(normalized_tx_id)
            for tx_item in item.get("transactionIds") or []:
                try:
                    normalized_tx_id = int(tx_item)
                except Exception:
                    continue
                if normalized_tx_id > 0 and normalized_tx_id not in transaction_ids:
                    transaction_ids.append(normalized_tx_id)
        return {
            "enabled": enabled,
            "charged": charged,
            "billingMode": "token_usage",
            "amount": str(amount.quantize(Decimal("0.01"))),
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": total_tokens,
            "providerCalls": provider_calls,
            "transactionId": transaction_ids[0] if len(transaction_ids) == 1 else None,
            "transactionIds": transaction_ids,
        }

    @staticmethod
    def _is_probable_text_followup(message: str) -> bool:
        normalized = re.sub(r"[\s，。！？、,.!?;；:：]+", "", str(message or "").strip())
        if not normalized:
            return False
        if any(marker in normalized for marker in _ASSISTANT_NEW_TASK_MARKERS):
            return False
        if len(normalized) <= 8:
            return True
        return len(normalized) <= 18 and any(marker in normalized for marker in _ASSISTANT_FOLLOWUP_MARKERS)

    @staticmethod
    def _is_unmatched_text_entry_context(
        *,
        entry_route_path: str,
        effective_route_path: str,
        context_params: dict[str, Any] | None,
        module_code: str | None,
    ) -> bool:
        normalized_entry = _normalize_route_path(entry_route_path)
        normalized_effective = _normalize_route_path(effective_route_path)
        normalized_module = str(module_code or "").strip()
        if not is_text_entry_route(normalized_entry, context_params):
            return False
        if normalized_module and normalized_module != "default":
            return False
        routing = (context_params or {}).get(routing_state_key()) if isinstance(context_params, dict) else None
        if not isinstance(routing, dict):
            return normalized_effective in {normalized_entry, "/", "/assistant", _MESSAGE_CHANNEL_ROUTE}
        routing_source = str(routing.get("source") or "").strip()
        if routing_source in {"tool_intent", "catalog", "adapter", "scope", "session_memory"}:
            return False
        active_route = _normalize_route_path(routing.get("activeRoutePath") or normalized_effective)
        return active_route in {normalized_entry, "/", "/assistant", _MESSAGE_CHANNEL_ROUTE}

    @staticmethod
    def _build_unmatched_text_entry_reply() -> str:
        return (
            "当前没有匹配到可调用的 AOJUAI 能力。"
            "请说明要处理的系统模块或业务对象；"
            "如果需要外部查询或实时信息能力，需要管理员先接入对应 Tool。"
        )

    @staticmethod
    def _extract_json_object(text: str | None) -> dict[str, Any] | None:
        source = str(text or "").strip()
        if not source:
            return None
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", source, flags=re.IGNORECASE)
        if fenced:
            source = fenced.group(1).strip()
        if not source.startswith("{"):
            start = source.find("{")
            end = source.rfind("}")
            if start >= 0 and end > start:
                source = source[start : end + 1]
        try:
            payload = json.loads(source)
        except (TypeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _planner_candidate_payload(candidate: AssistantExecutionPlan) -> dict[str, Any]:
        payload = {
            "routePath": candidate.route_path,
            "moduleCode": candidate.module_code,
            "moduleName": candidate.module_name,
            "toolId": candidate.tool_id,
            "summary": candidate.reason,
            "autoExecute": candidate.auto_execute,
            "scoreHint": candidate.confidence,
        }
        return {key: value for key, value in payload.items() if value not in (None, "", [])}

    @collects_usage("assistant:_call_ai_execution_planner")
    async def _call_ai_execution_planner(
        self,
        *,
        message: str,
        current_route_path: str,
        context_params: dict[str, Any] | None,
        session_context: dict[str, Any] | None,
        tenant_id: int,
        user_id: int,
        provider_settings: dict[str, Any] | None,
        billing_policy: Any | None = None,
        session_id: int | None = None,
        user_message_id: int | None = None,
    ) -> tuple[AssistantExecutionPlan | None, dict[str, Any] | None]:
        if not provider_settings:
            return None, None
        candidates = await AssistantExecutionPlanner(self.db).collect_candidates(
            message=message,
            current_route_path=current_route_path,
            context_params=context_params,
            session_context=session_context,
            tenant_id=tenant_id,
            user_id=user_id,
            limit=12,
        )
        if not candidates:
            return None, None

        candidate_payload = [self._planner_candidate_payload(item) for item in candidates]
        planner_prompt = (
            "你是 AOJUAI 的 Router Planner。你的任务不是回答用户，而是在已注册能力中选择执行范围。"
            "必须只基于候选 Tool/模块清单选择，不允许发明 Tool、外部能力或接口。"
            "本地候选分数只是检索提示，不是最终结论；请根据用户意图、模块名、Tool 名称和摘要自行判断。"
            "如果没有合适能力，返回 decision=none；如果需要用户补充才能判断，返回 decision=clarify。"
            "只返回一个 JSON 对象，不要 Markdown，不要解释。\n"
            "JSON 结构："
            "{\"decision\":\"tool|module|none|clarify\",\"toolId\":\"候选 toolId 或空\","
            "\"routePath\":\"候选 routePath 或当前入口\",\"moduleCode\":\"候选 moduleCode 或空\","
            "\"confidence\":0到1,\"reason\":\"一句话理由\"}"
        )
        user_payload = {
            "entryRoutePath": _normalize_route_path(current_route_path),
            "message": str(message or "").strip(),
            "candidates": candidate_payload,
        }
        planner_messages = [
            {"role": "system", "content": planner_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]
        billing_account_id = None
        if billing_policy is not None and bool(getattr(billing_policy, "enabled", False)):
            billing_account_id = await ensure_credit_precheck(
                credit_service=self.credit_service,
                tenant_id=tenant_id,
                user_id=user_id,
                policy=billing_policy,
            )
        raw, used_ai, usage = await self._call_ai_reply(
            tenant_id=tenant_id,
            provider_settings=provider_settings,
            messages=planner_messages,
        )
        if not used_ai:
            return None, None

        planner_billing_payload: dict[str, Any] | None = None
        if billing_policy is not None:
            planner_billing = await charge_credits_by_usage(
                credit_service=self.credit_service,
                tenant_id=tenant_id,
                user_id=user_id,
                policy=billing_policy,
                account_id=billing_account_id,
                reference_type="assistant_planner",
                reference_id=session_id,
                idempotency_key=(f"assistant_planner:{int(user_message_id)}" if user_message_id else None),
                remark="AI 助手 Planner 路由消耗",
                prompt_text=build_prompt_text_from_messages(planner_messages),
                completion_text=raw,
                usage=usage,
                extra={
                    "billing_source": "planner",
                    "entry_route_path": _normalize_route_path(current_route_path),
                    "candidate_count": len(candidates),
                    "session_id": session_id,
                },
            )
            planner_billing_payload = {
                **build_billing_result_payload(planner_billing, enabled=bool(getattr(billing_policy, "enabled", False))),
                "providerCalls": 1,
                "billingSource": "planner",
                "referenceType": "assistant_planner",
            }

        payload = self._extract_json_object(raw)
        if not payload:
            return None, planner_billing_payload
        decision = str(payload.get("decision") or "").strip().lower()
        if decision not in {"tool", "module"}:
            if planner_billing_payload is not None:
                planner_billing_payload["plannerDecision"] = decision or "none"
            return None, planner_billing_payload

        selected_tool_id = str(payload.get("toolId") or payload.get("tool_id") or "").strip()
        selected_route = _normalize_route_path(payload.get("routePath") or current_route_path)
        selected_module_code = str(payload.get("moduleCode") or payload.get("module_code") or "").strip()
        selected: AssistantExecutionPlan | None = None
        if selected_tool_id:
            selected = next((item for item in candidates if item.tool_id == selected_tool_id), None)
        if selected is None:
            selected = next(
                (
                    item
                    for item in candidates
                    if _normalize_route_path(item.route_path) == selected_route
                    and (not selected_module_code or item.module_code == selected_module_code)
                ),
                None,
            )
        if selected is None:
            if planner_billing_payload is not None:
                planner_billing_payload["plannerDecision"] = "rejected"
            return None, planner_billing_payload

        try:
            confidence = int(float(payload.get("confidence") or 0) * 100)
        except (TypeError, ValueError):
            confidence = 0
        reason = str(payload.get("reason") or selected.reason or "AI planner 选择候选能力").strip()
        if planner_billing_payload is not None:
            planner_billing_payload.update(
                {
                    "plannerDecision": decision,
                    "selectedToolId": selected.tool_id if decision == "tool" else None,
                    "selectedRoutePath": selected.route_path,
                    "selectedModuleCode": selected.module_code,
                }
            )
        return AssistantExecutionPlan(
            route_path=selected.route_path,
            module_code=selected.module_code,
            module_name=selected.module_name,
            confidence=max(1, min(confidence, 100)),
            source="ai_planner",
            reason=reason,
            intent_id=selected.intent_id,
            tool_id=selected.tool_id if decision == "tool" else None,
            auto_execute=selected.auto_execute if decision == "tool" else False,
            default_params=selected.default_params if decision == "tool" else None,
        ), planner_billing_payload

    async def _resolve_effective_turn_route(
        self,
        *,
        session: AssistantSession,
        message: str,
        bound_route_path: str,
        bound_context_params: dict[str, Any],
        tenant_id: int,
        user_id: int,
        provider_settings: dict[str, Any] | None = None,
        billing_policy: Any | None = None,
        user_message_id: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        session_context = dict(session.context_data or {}) if isinstance(session.context_data, dict) else {}
        normalized_bound_route = _normalize_route_path(bound_route_path)
        context_params = self._merge_internal_session_context(bound_context_params, session_context)
        existing_routing = self._extract_context_routing_state(context_params, session_context)
        text_entry = is_text_entry_route(normalized_bound_route, context_params)
        decision, planner_billing_payload = await self._call_ai_execution_planner(
            message=message,
            current_route_path=normalized_bound_route,
            context_params=context_params,
            session_context=session_context,
            tenant_id=tenant_id,
            user_id=user_id,
            provider_settings=provider_settings,
            billing_policy=billing_policy,
            session_id=getattr(session, "id", None),
            user_message_id=user_message_id,
        )
        if planner_billing_payload:
            context_params[_ASSISTANT_PLANNER_BILLING_KEY] = planner_billing_payload
        if decision is None and not provider_settings:
            decision = await AssistantExecutionPlanner(self.db).plan_turn(
                message=message,
                current_route_path=normalized_bound_route,
                context_params=context_params,
                session_context=session_context,
                tenant_id=tenant_id,
                user_id=user_id,
            )
        if decision is not None:
            effective_route = _normalize_route_path(decision.route_path)
            context_params[routing_state_key()] = {
                **decision.to_context(),
                "entryRoutePath": normalized_bound_route,
                "textEntry": text_entry,
            }
            return effective_route, context_params

        if (
            text_entry
            and isinstance(existing_routing, dict)
            and self._is_probable_text_followup(message)
        ):
            active_route = _normalize_route_path(existing_routing.get("activeRoutePath"))
            if active_route not in {"/", "/assistant", _MESSAGE_CHANNEL_ROUTE}:
                context_params[routing_state_key()] = {
                    **existing_routing,
                    "activeRoutePath": active_route,
                    "entryRoutePath": normalized_bound_route,
                    "source": "session_memory",
                    "reason": str(existing_routing.get("reason") or "沿用上一轮文本会话路由"),
                    "textEntry": True,
                }
                return active_route, context_params

        if text_entry:
            context_params[routing_state_key()] = {
                "activeRoutePath": normalized_bound_route,
                "activeModuleCode": None,
                "activeModuleName": None,
                "confidence": 0,
                "source": "text_entry",
                "reason": "当前文本入口未匹配到具体业务模块",
                "entryRoutePath": normalized_bound_route,
                "textEntry": True,
            }
            return normalized_bound_route, context_params

        if existing_routing and routing_state_key() not in context_params:
            context_params[routing_state_key()] = existing_routing
        return normalized_bound_route, context_params

    @staticmethod
    def _build_assistant_entry_context(
        *,
        entry_route_path: str,
        effective_route_path: str,
        context_params: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "entryRoutePath": _normalize_route_path(entry_route_path),
            "effectiveRoutePath": _normalize_route_path(effective_route_path),
            "source": str(context_params.get("source") or "").strip() or "web",
            "channelType": str(context_params.get("channelType") or "").strip() or None,
            "channelId": context_params.get("channelId"),
            "conversationId": str(context_params.get("conversationId") or "").strip() or None,
            "isMessageChannel": AssistantService._is_message_channel_context(entry_route_path, context_params),
        }
        return {key: value for key, value in payload.items() if value not in (None, "")}

    @classmethod
    def _attach_foundation_context(
        cls,
        *,
        context_data: dict[str, Any],
        entry_route_path: str,
        effective_route_path: str,
        context_params: dict[str, Any],
    ) -> dict[str, Any]:
        payload = dict(context_data or {})
        payload[_ASSISTANT_ENTRY_KEY] = cls._build_assistant_entry_context(
            entry_route_path=entry_route_path,
            effective_route_path=effective_route_path,
            context_params=context_params,
        )
        routing = context_params.get(routing_state_key())
        if isinstance(routing, dict) and routing:
            payload[routing_state_key()] = dict(routing)
        memory = context_params.get(_ASSISTANT_MEMORY_KEY)
        if isinstance(memory, dict) and memory:
            memory_payload = dict(memory)
            if isinstance(routing, dict) and routing:
                active_route = _normalize_route_path(routing.get("activeRoutePath"))
                memory_payload["activeRoutePath"] = active_route
                active_module_code = str(routing.get("activeModuleCode") or "").strip()
                active_module_name = str(routing.get("activeModuleName") or "").strip()
                if active_module_code:
                    memory_payload["activeModuleCode"] = active_module_code
                else:
                    memory_payload.pop("activeModuleCode", None)
                if active_module_name:
                    memory_payload["activeModuleName"] = active_module_name
                else:
                    memory_payload.pop("activeModuleName", None)
            payload[_ASSISTANT_MEMORY_KEY] = memory_payload
        return payload

    @staticmethod
    def _session_route_after_turn(
        *,
        entry_route_path: str,
        effective_route_path: str,
        context_params: dict[str, Any],
    ) -> str:
        if AssistantService._is_message_channel_context(entry_route_path, context_params):
            return _normalize_route_path(entry_route_path)
        return _normalize_route_path(effective_route_path)

    @staticmethod
    def _align_navigation_action_with_effective_route(
        action: dict[str, Any] | None,
        *,
        entry_route_path: str,
        effective_route_path: str,
        context_params: dict[str, Any],
    ) -> dict[str, Any] | None:
        normalized_action = normalize_assistant_action(action)
        if not normalized_action:
            return None
        if str(normalized_action.get("toolId") or "").strip() != "page.router.navigate":
            return normalized_action
        if AssistantService._is_message_channel_context(entry_route_path, context_params):
            return None
        entry_route = _normalize_route_path(entry_route_path)
        effective_route = _normalize_route_path(effective_route_path)
        if effective_route == entry_route:
            return normalized_action
        routing = context_params.get(routing_state_key())
        if not isinstance(routing, dict):
            return normalized_action
        routing_route = _normalize_route_path(routing.get("activeRoutePath"))
        if routing_route != effective_route:
            return normalized_action
        aligned_action = dict(normalized_action)
        aligned_action["targetRoutePath"] = effective_route
        target_module_code = str(routing.get("activeModuleCode") or "").strip()
        if target_module_code:
            aligned_action["targetModuleCode"] = target_module_code
        return aligned_action

    @staticmethod
    def _response_action_for_entry(
        *,
        action: dict[str, Any] | None,
        context_params: dict[str, Any],
        action_execution: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        normalized_action = normalize_assistant_action(action)
        if not normalized_action:
            return None
        if AssistantService._is_message_channel_context(
            str((context_params or {}).get("entryRoutePath") or ""),
            context_params,
        ):
            return None
        if action_execution is None:
            return normalized_action
        displayed_action = dict(normalized_action)
        displayed_action["mode"] = "result"
        displayed_action["canExecute"] = False
        displayed_action["autoExecute"] = False
        if str(action_execution.get("message") or "").strip():
            displayed_action["summary"] = str(action_execution.get("message") or "").strip()
        return displayed_action

    @staticmethod
    def _compact_response_role_profile(raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        payload: dict[str, Any] = {}
        for key in ("id", "label", "actorKind"):
            value = str(raw.get(key) or "").strip()
            if value:
                payload[key] = value
        for key in ("availableToolIds", "preferredToolIds"):
            values = [
                str(item or "").strip()
                for item in (raw.get(key) if isinstance(raw.get(key), list) else [])
                if str(item or "").strip()
            ][:12]
            if values:
                payload[key] = values
        return payload or None

    @staticmethod
    def _compact_response_skill_packs(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        items: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            skill_id = str(item.get("id") or "").strip()
            label = str(item.get("label") or skill_id).strip()
            if not skill_id and not label:
                continue
            items.append(
                {
                    "id": skill_id,
                    "label": label or skill_id,
                    "available": item.get("available") is not False,
                }
            )
            if len(items) >= 8:
                break
        return items

    @classmethod
    def _response_context_for_entry(
        cls,
        *,
        entry_route_path: str,
        context_params: dict[str, Any],
        context_data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if cls._is_message_channel_context(entry_route_path, context_params):
            return {}
        source = context_data if isinstance(context_data, dict) else {}
        payload: dict[str, Any] = {}
        role_profile = cls._compact_response_role_profile(source.get("currentRoleProfile"))
        if role_profile:
            payload["currentRoleProfile"] = role_profile
        skill_packs = cls._compact_response_skill_packs(source.get("skillPacks"))
        if skill_packs:
            payload["skillPacks"] = skill_packs
        for key in (_ASSISTANT_ENTRY_KEY, routing_state_key()):
            value = source.get(key)
            if isinstance(value, dict) and value:
                payload[key] = dict(value)
        return payload

    async def _get_user_team_ids(self, tenant_id: int, user_id: int) -> list[int]:
        result = await self.db.execute(
            select(UserTeam.team_id).where(
                UserTeam.tenant_id == tenant_id,
                UserTeam.user_id == user_id,
            )
        )
        return [int(item) for item in result.scalars().all()]

    def to_session_response(self, session: AssistantSession) -> SessionResponse:
        route_path = _normalize_route_path(session.route_path)
        adapter = self._resolve_adapter(route_path)
        return SessionResponse(
            id=session.id,
            module_code=session.module_code,
            module_name=adapter.module_name if adapter else None,
            route_path=route_path,
            context_data=dict(session.context_data or {}),
            created_at=session.created_at,
        )

    async def create_session(
        self,
        tenant_id: int,
        user_id: int,
        module_code: str | None,
        route_path: str,
        context_params: dict[str, Any],
    ) -> SessionResponse:
        from app.domain.assistant.config_service import AssistantConfigService

        await AssistantConfigService(self.db).ensure_enabled(tenant_id)

        normalized_route = _normalize_route_path(route_path)
        adapter = self._resolve_adapter(normalized_route)
        normalized_module_code = str(module_code or "").strip() or adapter.module_code
        session = AssistantSession(
            tenant_id=tenant_id,
            user_id=user_id,
            module_code=normalized_module_code,
            route_path=normalized_route,
            context_data=context_params or {},
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return self.to_session_response(session)

    async def list_sessions(
        self,
        tenant_id: int,
        user_id: int,
        limit: int = 20,
    ) -> list[SessionResponse]:
        from app.domain.assistant.config_service import AssistantConfigService

        await AssistantConfigService(self.db).ensure_enabled(tenant_id)

        result = await self.db.execute(
            select(AssistantSession)
            .where(
                AssistantSession.tenant_id == tenant_id,
                AssistantSession.user_id == user_id,
                AssistantSession.deleted_at.is_(None),
            )
            .order_by(AssistantSession.updated_at.desc().nullslast(), AssistantSession.id.desc())
            .limit(max(1, min(limit, 100)))
        )
        sessions = result.scalars().all()
        return [self.to_session_response(session) for session in sessions]

    async def get_session(
        self,
        session_id: int,
        tenant_id: int,
        user_id: int,
    ) -> AssistantSession:
        result = await self.db.execute(
            select(AssistantSession).where(
                AssistantSession.id == session_id,
                AssistantSession.tenant_id == tenant_id,
                AssistantSession.user_id == user_id,
                AssistantSession.deleted_at.is_(None),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError(resource="Session", resource_id=session_id)
        return session

    async def list_session_messages(
        self,
        *,
        session_id: int,
        tenant_id: int,
        user_id: int,
        limit: int = 100,
    ) -> list[MessageResponse]:
        from app.domain.assistant.config_service import AssistantConfigService

        await AssistantConfigService(self.db).ensure_enabled(tenant_id)
        session = await self.get_session(session_id=session_id, tenant_id=tenant_id, user_id=user_id)
        result = await self.db.execute(
            select(AssistantMessage)
            .where(
                AssistantMessage.session_id == session.id,
                AssistantMessage.deleted_at.is_(None),
            )
            .order_by(AssistantMessage.created_at.asc(), AssistantMessage.id.asc())
            .limit(max(1, min(limit, 200)))
        )
        messages = result.scalars().all()
        return [MessageResponse.model_validate(item) for item in messages]

    async def delete_session(
        self,
        session_id: int,
        tenant_id: int,
        user_id: int,
    ) -> None:
        from datetime import datetime

        from app.domain.assistant.config_service import AssistantConfigService

        await AssistantConfigService(self.db).ensure_enabled(tenant_id)
        session = await self.get_session(session_id=session_id, tenant_id=tenant_id, user_id=user_id)
        deleted_at = datetime.now(UTC)
        session.deleted_at = deleted_at
        result = await self.db.execute(
            select(AssistantMessage).where(
                AssistantMessage.session_id == session.id,
                AssistantMessage.deleted_at.is_(None),
            )
        )
        for message in result.scalars().all():
            message.deleted_at = deleted_at
        await self.db.commit()

    async def get_context(
        self,
        *,
        tenant_id: int,
        user_id: int,
        route_path: str,
        context_params: dict[str, Any] | None = None,
        team_ids: list[int] | None = None,
    ) -> ContextResponse:
        from app.domain.assistant.config_service import AssistantConfigService

        config_service = AssistantConfigService(self.db)
        await config_service.ensure_enabled(tenant_id)

        normalized_route = _normalize_route_path(route_path)
        adapter = self._resolve_adapter(normalized_route)
        viewer_team_ids = await self._get_user_team_ids(tenant_id, user_id)
        normalized_read_team_ids = self._derive_team_ids(team_ids)
        assistant_config = None
        if callable(getattr(self.db, "execute", None)):
            assistant_config = await config_service.get_config(tenant_id)
        context_data = await self._load_adapter_context_data(
            adapter=adapter,
            route_path=normalized_route,
            context_params=context_params or {},
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
            capability_config=self._extract_capability_config(assistant_config),
        )
        return ContextResponse(
            module_code=adapter.module_code,
            module_name=adapter.module_name,
            route_path=normalized_route,
            data=context_data,
        )

    async def _load_adapter_context_data(
        self,
        *,
        adapter: Any,
        route_path: str,
        context_params: dict[str, Any],
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None,
        capability_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context_data = await adapter.get_context(
            route_path,
            context_params,
            db=self.db,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
        )
        normalized_context = dict(context_data or {}) if isinstance(context_data, dict) else {}
        capability_source = await adapter.get_capability_source(
            route_path,
            context_params,
            context_data=normalized_context,
            db=self.db,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
        )
        if isinstance(capability_source, dict) and capability_source:
            merged_context = {
                **normalized_context,
                **capability_source,
            }
            return apply_module_skill_governance_to_context(
                module_code=str(getattr(adapter, "module_code", "") or "").strip(),
                context_data=merged_context,
                capability_config=capability_config,
            )
        return normalized_context

    async def get_presets(
        self,
        *,
        tenant_id: int,
        user_id: int,
        route_path: str,
        context_params: dict[str, Any] | None = None,
        team_ids: list[int] | None = None,
    ) -> PresetsResponse:
        from app.domain.assistant.config_service import AssistantConfigService

        await AssistantConfigService(self.db).ensure_enabled(tenant_id)

        normalized_route = _normalize_route_path(route_path)
        adapter = self._resolve_adapter(normalized_route)
        viewer_team_ids = await self._get_user_team_ids(tenant_id, user_id)
        normalized_read_team_ids = self._derive_team_ids(team_ids)
        presets = await adapter.get_presets(
            normalized_route,
            context_params or {},
            db=self.db,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
        )
        return PresetsResponse(
            module_code=adapter.module_code,
            module_name=adapter.module_name,
            route_path=normalized_route,
            presets=presets,
        )

    @staticmethod
    def _message_scope_snapshot(item: Any) -> dict[str, str]:
        action_result = item.action_result if isinstance(getattr(item, "action_result", None), dict) else {}
        module_code = str(action_result.get("moduleCode") or action_result.get("module_code") or "").strip()
        route_path = str(action_result.get("routePath") or action_result.get("route_path") or "").strip()
        return {
            "moduleCode": module_code,
            "routePath": _normalize_route_path(route_path) if route_path else "",
        }

    @classmethod
    def _build_compact_history_memory(
        cls,
        *,
        older_history: list[Any],
        session_context: dict[str, Any] | None,
        active_module_code: str | None,
        active_route_path: str | None,
    ) -> str:
        memory = (
            session_context.get(_ASSISTANT_MEMORY_KEY)
            if isinstance(session_context, dict) and isinstance(session_context.get(_ASSISTANT_MEMORY_KEY), dict)
            else None
        )
        lines: list[str] = [
            "【压缩会话记忆】以下内容只是长对话压缩摘要，用于连续性；不得覆盖当前路由、当前模块和本轮用户消息。",
        ]
        active_scope = " / ".join(
            part
            for part in (
                str(active_module_code or "").strip(),
                _normalize_route_path(active_route_path) if active_route_path else "",
            )
            if part
        )
        if active_scope:
            lines.append(f"当前有效范围：{active_scope}")
        if isinstance(memory, dict):
            working_summary = str(memory.get("workingSummary") or "").strip()
            if working_summary:
                lines.append(f"滚动摘要：{_trim_prompt_text(working_summary, limit=700)}")
            recent_modules = [
                str(item or "").strip()
                for item in (memory.get("recentModules") or [])
                if str(item or "").strip()
            ][:6]
            if recent_modules:
                lines.append(f"最近涉及模块：{'、'.join(recent_modules)}")
        if older_history:
            lines.append(f"已舍弃明细轮次：{len(older_history)} 条，仅保留下列高层摘要。")
            for item in older_history[-8:]:
                role = cls._normalize_role(getattr(item, "role", ""))
                if not role:
                    continue
                scope = cls._message_scope_snapshot(item)
                scope_label = " / ".join(
                    part
                    for part in (scope.get("moduleCode"), scope.get("routePath"))
                    if str(part or "").strip()
                )
                role_label = "用户" if role == "user" else "助手" if role == "assistant" else "系统"
                content = _trim_prompt_text(getattr(item, "content", ""), limit=120)
                if not content:
                    continue
                if scope_label:
                    lines.append(f"- {role_label}@{scope_label}: {content}")
                else:
                    lines.append(f"- {role_label}: {content}")
        lines.append("使用规则：如果用户切换模块或业务对象，只保留明确偏好/约束；业务事实必须重新依据当前模块上下文确认。")
        return _trim_prompt_text("\n".join(lines), limit=_ASSISTANT_MEMORY_TEXT_LIMIT)

    async def _build_chat_messages(
        self,
        *,
        session_id: int,
        session_context: dict[str, Any] | None = None,
        active_module_code: str | None = None,
        active_route_path: str | None = None,
    ) -> list[dict[str, str]]:
        result = await self.db.execute(
            select(AssistantMessage)
            .where(
                AssistantMessage.session_id == session_id,
                AssistantMessage.deleted_at.is_(None),
            )
            .order_by(AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
            .limit(_ASSISTANT_HISTORY_FETCH_LIMIT)
        )
        history = list(reversed(result.scalars().all()))
        older_history = history[:-_ASSISTANT_RECENT_HISTORY_LIMIT]
        recent_history = history[-_ASSISTANT_RECENT_HISTORY_LIMIT:]
        messages: list[dict[str, str]] = []
        memory_content = self._build_compact_history_memory(
            older_history=older_history,
            session_context=session_context,
            active_module_code=active_module_code,
            active_route_path=active_route_path,
        )
        if older_history or (
            isinstance(session_context, dict)
            and isinstance(session_context.get(_ASSISTANT_MEMORY_KEY), dict)
        ):
            messages.append({"role": "system", "content": memory_content})
        for item in recent_history:
            role = self._normalize_role(item.role)
            if not role:
                continue
            content = _trim_prompt_text(item.content, limit=_ASSISTANT_HISTORY_MESSAGE_CHAR_LIMIT)
            if role == "assistant" and isinstance(item.action_result, dict):
                content = (
                    f"{content}"
                    f"{build_action_history_suffix(item.action_result.get('assistantAction'))}"
                    f"{build_action_execution_history_suffix(item.action_result.get('actionExecution'))}"
                )
            messages.append({"role": role, "content": content.strip()})
        return messages

    @staticmethod
    def _assistant_action_matches_scope(
        *,
        action: dict[str, Any],
        action_result: dict[str, Any],
        module_code: str | None,
        route_path: str | None,
    ) -> bool:
        expected_module = str(module_code or "").strip()
        expected_route = _normalize_route_path(route_path) if route_path else ""
        result_module = str(action_result.get("moduleCode") or action_result.get("module_code") or "").strip()
        result_route = str(action_result.get("routePath") or action_result.get("route_path") or "").strip()
        normalized_result_route = _normalize_route_path(result_route) if result_route else ""
        if expected_module and result_module and expected_module != result_module:
            return False
        if expected_route and normalized_result_route and expected_route != normalized_result_route:
            return False
        tool_id = str(action.get("toolId") or "").strip()
        if expected_module and "." in tool_id:
            tool_module = tool_id.split(".", 1)[0].strip()
            if tool_module and tool_module not in {expected_module, expected_module.replace("-", "_")}:
                return False
        return True

    async def _get_last_assistant_action(
        self,
        *,
        session_id: int,
        module_code: str | None = None,
        route_path: str | None = None,
    ) -> dict[str, Any] | None:
        if not callable(getattr(self.db, "execute", None)):
            return None
        result = await self.db.execute(
            select(AssistantMessage)
            .where(
                AssistantMessage.session_id == session_id,
                AssistantMessage.role == MessageRole.ASSISTANT.value,
                AssistantMessage.deleted_at.is_(None),
            )
            .order_by(AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
            .limit(12)
        )
        history = result.scalars().all()
        latest_action_execution: dict[str, Any] | None = None
        for item in history:
            if not isinstance(item.action_result, dict):
                continue
            if latest_action_execution is None:
                raw_action_execution = item.action_result.get("actionExecution")
                if isinstance(raw_action_execution, dict):
                    latest_action_execution = summarize_action_execution(raw_action_execution)
            action = normalize_assistant_action(item.action_result.get("assistantAction"))
            if action:
                if not self._assistant_action_matches_scope(
                    action=action,
                    action_result=item.action_result,
                    module_code=module_code,
                    route_path=route_path,
                ):
                    continue
                if latest_action_execution is not None:
                    action["collectedParams"] = dict(action.get("collectedParams") or {})
                    action["collectedParams"][_ASSISTANT_LAST_ACTION_EXECUTION_KEY] = latest_action_execution
                return action
        return None

    @staticmethod
    def _extract_prior_execution_summary(
        prior_action: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        normalized_action = normalize_assistant_action(prior_action)
        if not normalized_action:
            return None
        collected_params = normalized_action.get("collectedParams")
        if not isinstance(collected_params, dict):
            return None
        raw_execution = collected_params.get(_ASSISTANT_LAST_ACTION_EXECUTION_KEY)
        if not isinstance(raw_execution, dict):
            return None
        summarized_execution = summarize_action_execution(raw_execution)
        if isinstance(summarized_execution, dict) and summarized_execution:
            return summarized_execution
        compacted_execution = compact_prompt_value(raw_execution, max_items=12)
        return compacted_execution if isinstance(compacted_execution, dict) and compacted_execution else None

    @staticmethod
    def _summarize_prior_action_for_prompt(
        prior_action: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        normalized_action = normalize_assistant_action(prior_action)
        if not normalized_action:
            return None
        payload: dict[str, Any] = {
            "toolId": str(normalized_action.get("toolId") or "").strip(),
            "mode": str(normalized_action.get("mode") or "").strip(),
            "summary": str(normalized_action.get("summary") or "").strip(),
            "confirmationRequired": normalized_action.get("confirmationRequired") is True,
            "canExecute": normalized_action.get("canExecute") is True,
        }
        collected_params = normalized_action.get("collectedParams")
        if isinstance(collected_params, dict):
            compacted_params: dict[str, Any] = {}
            for key, value in collected_params.items():
                normalized_key = str(key or "").strip()
                if not normalized_key or normalized_key.startswith(_ASSISTANT_INTERNAL_PARAM_PREFIX):
                    continue
                compacted_value = compact_prompt_value(value, max_items=6)
                if compacted_value is None:
                    continue
                compacted_params[normalized_key] = compacted_value
                if len(compacted_params) >= 12:
                    break
            if compacted_params:
                payload["collectedParams"] = compacted_params
        payload = {
            key: value
            for key, value in payload.items()
            if value not in (None, "", []) and (not isinstance(value, dict) or value)
        }
        return payload or None

    @classmethod
    def _build_prompt_context_payload(
        cls,
        *,
        adapter: Any,
        module_code: str,
        module_name: str,
        route_path: str,
        context_data: dict[str, Any],
        prior_action: dict[str, Any] | None,
    ) -> dict[str, Any]:
        builder = getattr(adapter, "build_prompt_context", None)
        if callable(builder):
            payload = builder(
                module_code=module_code,
                module_name=module_name,
                route=route_path,
                context_data=context_data if isinstance(context_data, dict) else {},
            )
            if isinstance(payload, dict) and payload:
                prompt_context = dict(payload)
            else:
                prompt_context = build_generic_prompt_context(
                    module_code=module_code,
                    module_name=module_name,
                    route_path=route_path,
                    context_data=context_data if isinstance(context_data, dict) else {},
                )
        else:
            prompt_context = build_generic_prompt_context(
                module_code=module_code,
                module_name=module_name,
                route_path=route_path,
                context_data=context_data if isinstance(context_data, dict) else {},
            )
        compact_prior_action = cls._summarize_prior_action_for_prompt(prior_action)
        if compact_prior_action is not None:
            prompt_context["priorAction"] = compact_prior_action
        compact_prior_execution = cls._extract_prior_execution_summary(prior_action)
        if compact_prior_execution is not None:
            prompt_context["priorExecution"] = compact_prior_execution
        for source_key, prompt_key in (
            (_ASSISTANT_ENTRY_KEY, "assistantEntry"),
            (routing_state_key(), "assistantRouting"),
            (_ASSISTANT_MEMORY_KEY, "assistantMemory"),
        ):
            compact_value = compact_prompt_value(
                context_data.get(source_key) if isinstance(context_data, dict) else None,
                max_items=8,
            )
            if compact_value:
                prompt_context[prompt_key] = compact_value
        return prompt_context

    @staticmethod
    def _extract_reply_payload(reply: str | None) -> tuple[str, dict[str, Any] | None]:
        plain_reply, action = extract_assistant_action(reply)
        return plain_reply.strip(), normalize_assistant_action(action)

    @staticmethod
    def _assistant_action_score(action: dict[str, Any] | None) -> tuple[int, int, int, int, int, int]:
        normalized = normalize_assistant_action(action)
        if not normalized:
            return (-1, -1, -1, -1, -1, -1)
        mode_score_map = {
            "blocked": 0,
            "collect": 1,
            "confirm": 2,
            "ready": 3,
            "result": 4,
        }
        return (
            1 if normalized.get("canExecute") is True else 0,
            mode_score_map.get(str(normalized.get("mode") or "").strip().lower(), 0),
            sum(
                1
                for value in (
                    normalized.get("toolLabel"),
                    normalized.get("skillId"),
                    normalized.get("skillLabel"),
                    normalized.get("summary"),
                )
                if str(value or "").strip()
            ),
            len(dict(normalized.get("collectedParams") or {})),
            -len(list(normalized.get("missingFields") or [])),
            1 if normalized.get("confirmationRequired") is False else 0,
        )

    @classmethod
    def _prefer_refined_action(
        cls,
        extracted_action: dict[str, Any] | None,
        inferred_action: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        normalized_extracted = normalize_assistant_action(extracted_action)
        normalized_inferred = normalize_assistant_action(inferred_action)
        if not normalized_inferred:
            return normalized_extracted
        if not normalized_extracted:
            return normalized_inferred
        if str(normalized_extracted.get("toolId") or "") != str(normalized_inferred.get("toolId") or ""):
            return normalized_extracted
        if cls._assistant_action_score(normalized_inferred) > cls._assistant_action_score(normalized_extracted):
            return normalized_inferred
        return normalized_extracted

    @classmethod
    def _select_assistant_action(
        cls,
        *,
        module_code: str | None = None,
        prefer_inferred_action_on_conflict: bool | None = None,
        extracted_action: dict[str, Any] | None,
        inferred_action: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        normalized_extracted = normalize_assistant_action(extracted_action)
        normalized_inferred = normalize_assistant_action(inferred_action)
        del module_code
        prefer_inferred = bool(prefer_inferred_action_on_conflict)
        if not prefer_inferred:
            return cls._prefer_refined_action(normalized_extracted, normalized_inferred)
        if not normalized_inferred:
            return normalized_extracted
        if not normalized_extracted:
            return normalized_inferred
        if str(normalized_extracted.get("toolId") or "") == str(normalized_inferred.get("toolId") or ""):
            return cls._prefer_refined_action(normalized_extracted, normalized_inferred)
        return normalized_inferred

    async def _infer_adapter_action(
        self,
        *,
        route_path: str,
        source_text: str,
        context_params: dict[str, Any],
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None,
        prior_action: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        normalized_source = str(source_text or "").strip()
        if not normalized_source:
            return None
        adapter = self._resolve_adapter(route_path)
        return await adapter.infer_action_from_reply(
            normalized_source,
            route_path,
            context_params,
            db=self.db,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
            prior_action=prior_action,
        )

    async def _infer_best_adapter_action(
        self,
        *,
        route_path: str,
        user_message: str,
        reply_text: str,
        context_params: dict[str, Any],
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None,
        prior_action: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        adapter = self._resolve_adapter(route_path)
        allow_user_message_inference = bool(getattr(adapter, "allow_user_message_inference", True))
        allow_reply_text_inference = bool(getattr(adapter, "allow_reply_text_inference", True))
        normalized_user_message = str(user_message or "").strip()
        normalized_reply_text = str(reply_text or "").strip()
        user_action = None
        if allow_user_message_inference and normalized_user_message:
            user_action = await self._infer_adapter_action(
                route_path=route_path,
                source_text=normalized_user_message,
                context_params=context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=read_team_ids,
                prior_action=prior_action,
            )
        if not normalized_reply_text or not allow_reply_text_inference:
            return user_action
        combined_text = "\n".join(
            part
            for part in (normalized_user_message, normalized_reply_text)
            if str(part or "").strip()
        )
        combined_action = await self._infer_adapter_action(
            route_path=route_path,
            source_text=combined_text,
            context_params=context_params,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
            prior_action=prior_action,
        )
        if not user_action:
            return combined_action
        if not combined_action:
            return user_action
        return self._prefer_refined_action(user_action, combined_action)

    async def _canonicalize_assistant_action(
        self,
        *,
        adapter: Any,
        route_path: str,
        action: dict[str, Any] | None,
        context_params: dict[str, Any],
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None,
        prior_action: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        normalized_action = normalize_assistant_action(action)
        if not normalized_action:
            return None
        canonicalize = getattr(adapter, "canonicalize_action", None)
        if not callable(canonicalize):
            return normalized_action
        canonical_action = await canonicalize(
            normalized_action,
            route_path,
            context_params,
            db=self.db,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
            prior_action=prior_action,
        )
        return normalize_assistant_action(canonical_action)

    async def _select_canonical_assistant_action(
        self,
        *,
        route_path: str,
        module_code: str,
        extracted_action: dict[str, Any] | None,
        inferred_action: dict[str, Any] | None,
        context_params: dict[str, Any],
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None,
        action_context_data: dict[str, Any] | None = None,
        capability_config: dict[str, Any] | None = None,
        prior_action: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        adapter = self._resolve_adapter(route_path)
        normalized_extracted = await self._canonicalize_assistant_action(
            adapter=adapter,
            route_path=route_path,
            action=extracted_action,
            context_params=context_params,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
            prior_action=prior_action,
        )
        normalized_extracted, _ = apply_module_skill_governance_to_action(
            module_code=module_code,
            action=normalized_extracted,
            context_data=action_context_data,
            capability_config=capability_config,
            builtin_tool_ids=self._assistant_builtin_tool_ids(),
        )
        normalized_inferred = await self._canonicalize_assistant_action(
            adapter=adapter,
            route_path=route_path,
            action=inferred_action,
            context_params=context_params,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
            prior_action=prior_action,
        )
        normalized_inferred, _ = apply_module_skill_governance_to_action(
            module_code=module_code,
            action=normalized_inferred,
            context_data=action_context_data,
            capability_config=capability_config,
            builtin_tool_ids=self._assistant_builtin_tool_ids(),
        )
        return self._select_assistant_action(
            module_code=module_code,
            prefer_inferred_action_on_conflict=getattr(adapter, "prefer_inferred_action_on_conflict", None),
            extracted_action=normalized_extracted,
            inferred_action=normalized_inferred,
        )

    async def _load_action_guard_context(
        self,
        *,
        adapter: Any,
        route_path: str,
        context_params: dict[str, Any],
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None,
    ) -> dict[str, Any] | None:
        if not callable(getattr(adapter, "get_context", None)):
            return None
        try:
            return await self._load_adapter_context_data(
                adapter=adapter,
                route_path=route_path,
                context_params=context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=read_team_ids,
                capability_config=None,
            )
        except Exception:
            return None

    async def _resolve_prompt_stack(
        self,
        *,
        tenant_id: int,
        module_code: str,
        module_name: str,
        default_module_chat_prompt: str | None = None,
    ) -> dict[str, str]:
        from app.domain.assistant.config_service import AssistantConfigService

        config_service = AssistantConfigService(self.db)
        return await config_service.get_prompt_stack(
            tenant_id=tenant_id,
            module_code=module_code,
            module_name=module_name,
            default_module_chat_prompt=default_module_chat_prompt,
        )

    @staticmethod
    def _extract_capability_config(assistant_config: Any) -> dict[str, Any]:
        config_payload = assistant_config.config if assistant_config and isinstance(assistant_config.config, dict) else {}
        capabilities = config_payload.get("capabilities")
        return capabilities if isinstance(capabilities, dict) else {}

    @staticmethod
    def _assistant_builtin_tool_ids() -> set[str]:
        return {
            str(item.get("id") or "").strip()
            for item in assistant_builtin_tool_catalog()
            if str(item.get("id") or "").strip()
        }

    @staticmethod
    def _find_tool_catalog_item(
        *,
        action: dict[str, Any] | None,
        context_data: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        normalized_action = normalize_assistant_action(action)
        if not normalized_action:
            return None
        tool_id = str(normalized_action.get("toolId") or "").strip()
        if not tool_id:
            return None
        raw_tool_catalog = (context_data or {}).get("toolCatalog") if isinstance(context_data, dict) else None
        if not isinstance(raw_tool_catalog, list):
            return None
        for item in raw_tool_catalog:
            if not isinstance(item, dict):
                continue
            if str(item.get("id") or "").strip() == tool_id:
                return dict(item)
        return None

    @classmethod
    def _build_unavailable_action_reply(
        cls,
        *,
        action: dict[str, Any] | None,
        context_data: dict[str, Any] | None,
        blocked_reason: str | None = None,
    ) -> str | None:
        normalized_action = normalize_assistant_action(action)
        if not normalized_action:
            return None
        tool_id = str(normalized_action.get("toolId") or "").strip()
        if not tool_id:
            return None
        tool = cls._find_tool_catalog_item(action=normalized_action, context_data=context_data)
        label = str((tool or {}).get("label") or normalized_action.get("toolLabel") or tool_id).strip() or tool_id
        reason = str((tool or {}).get("availabilityReason") or blocked_reason or "").strip() or "当前能力暂不可用"
        if "缺少所需权限" in reason:
            return f"当前账号暂无「{label}」权限，无法完成这次查询。"
        return f"当前无法使用「{label}」：{reason}。"

    @classmethod
    def _preplanned_action_blocked_reply(
        cls,
        *,
        action: dict[str, Any] | None,
        module_code: str,
        context_data: dict[str, Any] | None,
        capability_config: dict[str, Any] | None,
        builtin_tool_ids: set[str] | None = None,
    ) -> str | None:
        normalized_action = normalize_assistant_action(action)
        if not normalized_action:
            return None
        governed_action, blocked_reason = apply_module_skill_governance_to_action(
            module_code=module_code,
            action=normalized_action,
            context_data=context_data,
            capability_config=capability_config,
            builtin_tool_ids=builtin_tool_ids,
        )
        if governed_action is not None:
            return None
        return cls._build_unavailable_action_reply(
            action=normalized_action,
            context_data=context_data,
            blocked_reason=blocked_reason,
        )

    @staticmethod
    def _planned_action_from_routing_state(
        *,
        context_params: dict[str, Any] | None,
        context_data: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        routing = (context_params or {}).get(routing_state_key()) if isinstance(context_params, dict) else None
        if not isinstance(routing, dict) or routing.get("autoExecute") is not True:
            return None
        tool_id = str(routing.get("activeToolId") or "").strip()
        if not tool_id:
            return None

        tool_label = tool_id
        raw_tool_catalog = (context_data or {}).get("toolCatalog") if isinstance(context_data, dict) else None
        if isinstance(raw_tool_catalog, list):
            for item in raw_tool_catalog:
                if not isinstance(item, dict) or str(item.get("id") or "").strip() != tool_id:
                    continue
                tool_label = str(item.get("label") or tool_id).strip() or tool_id
                break

        collected_params = dict(routing.get("collectedParams") or {}) if isinstance(routing.get("collectedParams"), dict) else {}
        return {
            "version": 1,
            "toolId": tool_id,
            "toolLabel": tool_label,
            "mode": "ready",
            "summary": str(routing.get("reason") or tool_label or "准备执行查询。").strip(),
            "targetRoutePath": _normalize_route_path(routing.get("activeRoutePath") or ""),
            "targetModuleCode": str(routing.get("activeModuleCode") or "").strip() or None,
            "collectedParams": collected_params,
            "missingFields": [],
            "confirmationRequired": False,
            "canExecute": True,
            "autoExecute": True,
            "confirmText": "执行查询",
        }

    @classmethod
    def _should_auto_execute_chat_action(
        cls,
        *,
        action: dict[str, Any] | None,
        context_data: dict[str, Any] | None,
    ) -> bool:
        normalized_action = normalize_assistant_action(action)
        if not normalized_action:
            return False
        tool_id = str(normalized_action.get("toolId") or "").strip()
        if not tool_id or tool_id == "page.router.navigate":
            return False
        if normalized_action.get("autoExecute") is not True:
            return False
        if normalized_action.get("canExecute") is not True:
            return False
        if normalized_action.get("confirmationRequired") is True:
            return False
        if normalized_action.get("missingFields"):
            return False

        tool = cls._find_tool_catalog_item(action=normalized_action, context_data=context_data)
        if not tool or tool.get("available") is False or tool.get("confirmationRequired") is True:
            return False
        access_mode = str(tool.get("accessMode") or "").strip().lower()
        tool_type = str(tool.get("toolType") or "").strip().lower()
        mode = str(tool.get("mode") or "").strip().lower()
        return access_mode in {"read", "query"} or tool_type == "query" or mode == "query"

    async def _execute_action_runtime(
        self,
        *,
        adapter: Any,
        action_type: str,
        params: dict[str, Any] | None,
        route_path: str,
        context_params: dict[str, Any] | None,
        action_context_data: dict[str, Any] | None,
        capability_config: dict[str, Any] | None,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None,
    ) -> ActionResult:
        normalized_route_path = _normalize_route_path(route_path)
        normalized_params = dict(params or {})
        normalized_context_params = dict(context_params or {}) if isinstance(context_params, dict) else {}
        normalized_params["routePath"] = normalized_route_path
        normalized_params["route_path"] = normalized_route_path
        normalized_params.setdefault("contextParams", dict(normalized_context_params))
        normalized_params.setdefault("context_params", dict(normalized_context_params))

        guard_context = action_context_data
        if guard_context is None:
            guard_context = await self._load_action_guard_context(
                adapter=adapter,
                route_path=normalized_route_path,
                context_params=normalized_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=read_team_ids,
            )

        _governed_action, blocked_reason = apply_module_skill_governance_to_action(
            module_code=adapter.module_code,
            action={
                "toolId": action_type,
                "collectedParams": normalized_params,
            },
            context_data=guard_context,
            capability_config=capability_config,
            builtin_tool_ids=self._assistant_builtin_tool_ids(),
        )
        if _governed_action is None:
            message = str(blocked_reason or "当前动作不可用。").strip() or "当前动作不可用。"
            return ActionResult(
                success=False,
                data={
                    "blocked": True,
                    "reason": blocked_reason,
                    "actionType": action_type,
                },
                message=message,
            )

        async def _load_bound_context() -> dict[str, Any]:
            return await self._load_adapter_context_data(
                adapter=adapter,
                route_path=normalized_route_path,
                context_params=normalized_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=read_team_ids,
                capability_config=capability_config,
            )

        result = await execute_assistant_builtin_tool(
            action_type=action_type,
            params=normalized_params,
            route_path=normalized_route_path,
            module_code=adapter.module_code,
            context_data=normalized_context_params,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
            context_loader=_load_bound_context,
        )
        if result is not None:
            return result
        result = await self._execute_registered_tool_binding(
            adapter=adapter,
            action_type=action_type,
            params=normalized_params,
            route_path=normalized_route_path,
            context_params=normalized_context_params,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
        )
        if result is not None:
            return result
        return await adapter.execute_action(
            action=action_type,
            params=normalized_params,
            db=self.db,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
        )

    async def _execute_registered_tool_binding(
        self,
        *,
        adapter: Any,
        action_type: str,
        params: dict[str, Any],
        route_path: str,
        context_params: dict[str, Any],
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None,
    ) -> ActionResult | None:
        from app.domain.assistant.toolset_registry import (
            build_registered_execution_binding_map,
            get_assistant_module_toolset,
        )

        module_code = str(getattr(adapter, "module_code", "") or "").strip()
        toolset = get_assistant_module_toolset(module_code)
        if toolset is None and "." in str(action_type or ""):
            toolset = get_assistant_module_toolset(str(action_type).split(".", 1)[0])
        if toolset is None:
            return None
        binding = build_registered_execution_binding_map(toolset).get(str(action_type or "").strip())
        if binding is None or not callable(getattr(binding, "executor", None)):
            return None

        kwargs = {
            "db": self.db,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "viewer_team_ids": viewer_team_ids,
            "read_team_ids": read_team_ids,
            "params": params,
            "route_path": route_path,
            "context_params": context_params,
            "runtime_options": dict(getattr(binding, "runtime_options", {}) or {}),
        }
        executor = binding.executor
        try:
            signature = inspect.signature(executor)
            accepts_kwargs = any(
                parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in signature.parameters.values()
            )
            if not accepts_kwargs:
                kwargs = {key: value for key, value in kwargs.items() if key in signature.parameters}
        except (TypeError, ValueError):
            pass
        raw_result = executor(**kwargs)
        if inspect.isawaitable(raw_result):
            raw_result = await raw_result
        if isinstance(raw_result, ActionResult):
            return raw_result
        if isinstance(raw_result, dict):
            return ActionResult(
                success=bool(raw_result.get("success", True)),
                data=dict(raw_result.get("data") or raw_result),
                message=str(raw_result.get("message") or "").strip() or None,
            )
        if raw_result is None:
            return None
        return ActionResult(success=True, data={"result": raw_result}, message=str(raw_result or "").strip() or None)

    async def _execute_auto_chat_action(
        self,
        *,
        adapter: Any,
        assistant_action: dict[str, Any] | None,
        route_path: str,
        context_params: dict[str, Any] | None,
        action_context_data: dict[str, Any] | None,
        capability_config: dict[str, Any] | None,
        tenant_id: int,
        user_id: int,
        viewer_team_ids: list[int],
        read_team_ids: list[int] | None,
    ) -> dict[str, Any] | None:
        normalized_action = normalize_assistant_action(assistant_action)
        if not self._should_auto_execute_chat_action(action=normalized_action, context_data=action_context_data):
            return None
        action_type = str(normalized_action.get("toolId") or "").strip()
        result = await self._execute_action_runtime(
            adapter=adapter,
            action_type=action_type,
            params=dict(normalized_action.get("collectedParams") or {}),
            route_path=route_path,
            context_params=context_params,
            action_context_data=action_context_data,
            capability_config=capability_config,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=read_team_ids,
        )
        message = str(result.message or "").strip() or ("操作执行成功" if result.success else "操作执行失败")
        return {
            "actionType": action_type,
            "success": bool(result.success),
            "message": message,
            "result": result.data or {},
        }

    @staticmethod
    def _build_ai_client(provider_settings: dict[str, Any]):
        from app.domain.assistant.openai_client import OpenAIClient

        return OpenAIClient(
            base_url=provider_settings["base_url"],
            api_key=provider_settings["api_key"],
            model=provider_settings["model"],
            temperature=provider_settings["temperature"],
            max_tokens=provider_settings["max_tokens"],
        )

    async def _call_ai_reply(
        self,
        *,
        tenant_id: int,
        messages: list[dict[str, str]],
        provider_settings: dict[str, Any] | None = None,
    ) -> tuple[str, bool, dict[str, int]]:
        from app.domain.assistant.config_service import AssistantConfigService

        if provider_settings is None:
            provider_settings = await AssistantConfigService(self.db).get_provider_settings(tenant_id)
        if not provider_settings:
            return "", False, {}

        for attempt, delay_seconds in enumerate(_ASSISTANT_AI_RETRY_DELAYS, start=1):
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            client = self._build_ai_client(provider_settings)
            try:
                text, usage = await client.chat_with_usage(messages, stream=False)
                text = str(text or "").strip()
                return text, bool(text), usage
            except Exception as exc:
                logger.warning(
                    "assistant_ai_reply_failed",
                    tenant_id=tenant_id,
                    attempt=attempt,
                    max_attempts=len(_ASSISTANT_AI_RETRY_DELAYS),
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
        return "", False, {}

    @classmethod
    def _build_next_session_memory(
        cls,
        *,
        existing_context: dict[str, Any] | None,
        module_code: str,
        module_name: str,
        route_path: str,
        user_message: str,
        assistant_reply: str,
        assistant_action: dict[str, Any] | None,
    ) -> dict[str, Any]:
        previous_memory = (
            existing_context.get(_ASSISTANT_MEMORY_KEY)
            if isinstance(existing_context, dict) and isinstance(existing_context.get(_ASSISTANT_MEMORY_KEY), dict)
            else {}
        )
        normalized_route = _normalize_route_path(route_path)
        routing = (
            existing_context.get(routing_state_key())
            if isinstance(existing_context, dict) and isinstance(existing_context.get(routing_state_key()), dict)
            else {}
        )
        routing_route = _normalize_route_path(routing.get("activeRoutePath")) if routing else ""
        routing_module_code = str(routing.get("activeModuleCode") or "").strip() if routing else ""
        routing_module_name = str(routing.get("activeModuleName") or "").strip() if routing else ""
        resolved_module_code = str(module_code or "").strip()
        resolved_module_name = str(module_name or module_code or "").strip()
        if resolved_module_code == "default" and routing_module_code and routing_route == normalized_route:
            resolved_module_code = routing_module_code
            resolved_module_name = routing_module_name or routing_module_code
        module_label = str(resolved_module_name or resolved_module_code or "").strip()
        turn_summary = {
            "moduleCode": resolved_module_code,
            "moduleName": module_label,
            "routePath": normalized_route,
            "user": _trim_prompt_text(user_message, limit=180),
            "assistant": _trim_prompt_text(assistant_reply, limit=220),
        }
        action = normalize_assistant_action(assistant_action)
        if action:
            tool_id = str(action.get("toolId") or "").strip()
            summary = str(action.get("summary") or "").strip()
            if tool_id:
                turn_summary["toolId"] = tool_id
            if summary:
                turn_summary["actionSummary"] = _trim_prompt_text(summary, limit=160)

        previous_turns = [
            dict(item)
            for item in (previous_memory.get("recentTurns") or [])
            if isinstance(item, dict)
        ]
        recent_turns = [*previous_turns, turn_summary][-_ASSISTANT_MEMORY_TURN_LIMIT:]
        previous_modules = [
            str(item or "").strip()
            for item in (previous_memory.get("recentModules") or [])
            if str(item or "").strip()
        ]
        current_module = resolved_module_code
        recent_modules: list[str] = []
        for item in [current_module, *previous_modules]:
            if item and item not in recent_modules:
                recent_modules.append(item)
            if len(recent_modules) >= 8:
                break
        summary_lines = []
        for item in recent_turns[-6:]:
            scope = " / ".join(
                part
                for part in (
                    str(item.get("moduleCode") or "").strip(),
                    str(item.get("routePath") or "").strip(),
                )
                if part
            )
            user_text = str(item.get("user") or "").strip()
            assistant_text = str(item.get("assistant") or item.get("actionSummary") or "").strip()
            if not user_text and not assistant_text:
                continue
            prefix = f"{scope}: " if scope else ""
            summary_lines.append(
                _trim_prompt_text(
                    f"{prefix}用户「{user_text}」；助手「{assistant_text}」",
                    limit=260,
                )
            )
        working_summary = _tail_trim_prompt_text("\n".join(summary_lines), limit=_ASSISTANT_MEMORY_TEXT_LIMIT)
        return {
            "version": 1,
            "activeModuleCode": current_module,
            "activeModuleName": module_label,
            "activeRoutePath": normalized_route,
            "recentModules": recent_modules,
            "recentTurns": recent_turns,
            "workingSummary": working_summary,
            "policy": "压缩记忆只保留长期偏好、已确认约束和最近模块切换；当前事实以本轮路由上下文为准。",
        }

    @classmethod
    def _build_persisted_session_context(
        cls,
        *,
        context_params: dict[str, Any],
        session_context: dict[str, Any] | None,
        module_code: str,
        module_name: str,
        route_path: str,
        user_message: str,
        assistant_reply: str,
        assistant_action: dict[str, Any] | None,
    ) -> dict[str, Any]:
        persisted = cls._merge_internal_session_context(context_params, session_context)
        persisted.pop(_ASSISTANT_PLANNER_BILLING_KEY, None)
        persisted[_ASSISTANT_MEMORY_KEY] = cls._build_next_session_memory(
            existing_context=persisted,
            module_code=module_code,
            module_name=module_name,
            route_path=route_path,
            user_message=user_message,
            assistant_reply=assistant_reply,
            assistant_action=assistant_action,
        )
        return persisted

    @collects_usage("assistant:chat_reply")
    async def chat_reply(
        self,
        *,
        session_id: int,
        message: str,
        tenant_id: int,
        user_id: int,
        team_ids: list[int] | None = None,
        route_path: str | None = None,
        context_params: dict[str, Any] | None = None,
    ) -> ChatReplyResponse:
        from app.domain.assistant.config_service import AssistantConfigService

        config_service = AssistantConfigService(self.db)
        await config_service.ensure_enabled(tenant_id)
        assistant_config = await config_service.get_config(tenant_id)
        session = await self.get_session(session_id=session_id, tenant_id=tenant_id, user_id=user_id)
        bound_route_path = _normalize_route_path(route_path or session.route_path)
        bound_context_params = (
            dict(context_params)
            if isinstance(context_params, dict)
            else dict(session.context_data or {}) if isinstance(session.context_data, dict) else {}
        )

        normalized_message = str(message or "").strip()
        if not normalized_message:
            return ChatReplyResponse(
                session_id=session.id,
                module_code=session.module_code,
                module_name=self._resolve_adapter(bound_route_path).module_name,
                route_path=bound_route_path,
                reply="请输入你的问题。",
                used_ai=False,
                context={},
                suggestions=[],
            )

        provider_settings = await config_service.get_provider_settings(tenant_id)
        billing_policy = self._build_billing_policy_from_config(assistant_config)
        user_message = AssistantMessage(
            tenant_id=tenant_id,
            session_id=session.id,
            role=MessageRole.USER.value,
            content=normalized_message,
        )
        self.db.add(user_message)
        flush = getattr(self.db, "flush", None)
        if callable(flush):
            result = flush()
            if inspect.isawaitable(result):
                await result
        effective_route_path, bound_context_params = await self._resolve_effective_turn_route(
            session=session,
            message=normalized_message,
            bound_route_path=bound_route_path,
            bound_context_params=bound_context_params,
            tenant_id=tenant_id,
            user_id=user_id,
            provider_settings=provider_settings,
            billing_policy=billing_policy,
            user_message_id=user_message.id,
        )
        await self.db.commit()

        context = await self.get_context(
            tenant_id=tenant_id,
            user_id=user_id,
            route_path=effective_route_path,
            context_params=bound_context_params,
            team_ids=team_ids,
        )
        if isinstance(context.data, dict):
            context.data = self._attach_foundation_context(
                context_data=context.data,
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
            )
        user_message.action_result = {
            "moduleCode": context.module_code,
            "routePath": context.route_path,
            "entryRoutePath": bound_route_path,
        }
        viewer_team_ids = await self._get_user_team_ids(tenant_id, user_id)
        normalized_read_team_ids = self._derive_team_ids(team_ids)
        presets = await self.get_presets(
            tenant_id=tenant_id,
            user_id=user_id,
            route_path=effective_route_path,
            context_params=bound_context_params,
            team_ids=team_ids,
        )
        adapter = self._resolve_adapter(context.route_path)
        prior_action = await self._get_last_assistant_action(
            session_id=session.id,
            module_code=context.module_code,
            route_path=context.route_path,
        )
        planner_used_ai = self._routing_used_ai(bound_context_params)
        planner_billing_payload = self._planner_billing_payload(bound_context_params)
        capability_config = self._extract_capability_config(assistant_config)
        if provider_settings:
            pre_inferred_action = self._planned_action_from_routing_state(
                context_params=bound_context_params,
                context_data=context.data if isinstance(context.data, dict) else {},
            )
        else:
            pre_inferred_action = await self._infer_best_adapter_action(
                route_path=context.route_path,
                user_message=normalized_message,
                reply_text="",
                context_params=bound_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=normalized_read_team_ids,
                prior_action=prior_action,
            )
            if pre_inferred_action is None:
                pre_inferred_action = self._planned_action_from_routing_state(
                    context_params=bound_context_params,
                    context_data=context.data if isinstance(context.data, dict) else {},
                )
        blocked_action_reply = self._preplanned_action_blocked_reply(
            action=pre_inferred_action,
            module_code=context.module_code,
            context_data=context.data if isinstance(context.data, dict) else {},
            capability_config=capability_config,
            builtin_tool_ids=self._assistant_builtin_tool_ids(),
        )
        if blocked_action_reply:
            assistant_message = AssistantMessage(
                tenant_id=tenant_id,
                session_id=session.id,
                role=MessageRole.ASSISTANT.value,
                content=blocked_action_reply,
                action_type="chat_reply",
                action_result={
                    "moduleCode": context.module_code,
                    "routePath": context.route_path,
                    "usedAi": planner_used_ai,
                    "assistantAction": None,
                    "actionExecution": None,
                    "boundary": "action_unavailable",
                    "billing": self._merge_billing_payloads(planner_billing_payload),
                    "plannerBilling": planner_billing_payload,
                },
            )
            self.db.add(assistant_message)
            session.module_code = context.module_code
            session.route_path = self._session_route_after_turn(
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
            )
            session.context_data = self._build_persisted_session_context(
                context_params=bound_context_params,
                session_context=dict(session.context_data or {}) if isinstance(session.context_data, dict) else {},
                module_code=context.module_code,
                module_name=context.module_name,
                route_path=context.route_path,
                user_message=normalized_message,
                assistant_reply=blocked_action_reply,
                assistant_action=None,
            )
            await self.db.commit()
            return ChatReplyResponse(
                session_id=session.id,
                module_code=context.module_code,
                module_name=context.module_name,
                route_path=context.route_path,
                reply=blocked_action_reply,
                used_ai=planner_used_ai,
                context=self._response_context_for_entry(
                    entry_route_path=bound_route_path,
                    context_params=bound_context_params,
                    context_data=context.data if isinstance(context.data, dict) else {},
                ),
                suggestions=[item.prompt for item in presets.presets[:3]],
                action=None,
            )
        pre_auto_action_context = context.data if isinstance(context.data, dict) else {}
        pre_auto_action = await self._select_canonical_assistant_action(
            route_path=context.route_path,
            module_code=context.module_code,
            extracted_action=None,
            inferred_action=pre_inferred_action,
            context_params=bound_context_params,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
            action_context_data=pre_auto_action_context,
            capability_config=capability_config,
            prior_action=prior_action,
        )
        pre_auto_action = self._align_navigation_action_with_effective_route(
            pre_auto_action,
            entry_route_path=bound_route_path,
            effective_route_path=context.route_path,
            context_params=bound_context_params,
        )
        pre_action_execution = await self._execute_auto_chat_action(
            adapter=adapter,
            assistant_action=pre_auto_action,
            route_path=context.route_path,
            context_params=bound_context_params,
            action_context_data=pre_auto_action_context,
            capability_config=capability_config,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
        )
        if pre_action_execution is not None:
            reply = str(pre_action_execution.get("message") or "").strip() or "查询已完成。"
            assistant_message = AssistantMessage(
                tenant_id=tenant_id,
                session_id=session.id,
                role=MessageRole.ASSISTANT.value,
                content=reply,
                action_type="chat_reply",
                action_result={
                    "moduleCode": context.module_code,
                    "routePath": context.route_path,
                    "usedAi": planner_used_ai,
                    "assistantAction": pre_auto_action,
                    "actionExecution": pre_action_execution,
                    "boundary": "auto_read_tool",
                    "billing": self._merge_billing_payloads(planner_billing_payload),
                    "plannerBilling": planner_billing_payload,
                },
            )
            self.db.add(assistant_message)
            session.module_code = context.module_code
            session.route_path = self._session_route_after_turn(
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
            )
            session.context_data = self._build_persisted_session_context(
                context_params=bound_context_params,
                session_context=dict(session.context_data or {}) if isinstance(session.context_data, dict) else {},
                module_code=context.module_code,
                module_name=context.module_name,
                route_path=context.route_path,
                user_message=normalized_message,
                assistant_reply=reply,
                assistant_action=pre_auto_action,
            )
            await self.db.commit()
            response_action = self._response_action_for_entry(
                action=pre_auto_action,
                context_params=bound_context_params,
                action_execution=pre_action_execution,
            )
            return ChatReplyResponse(
                session_id=session.id,
                module_code=context.module_code,
                module_name=context.module_name,
                route_path=context.route_path,
                reply=reply,
                used_ai=planner_used_ai,
                context=self._response_context_for_entry(
                    entry_route_path=bound_route_path,
                    context_params=bound_context_params,
                    context_data=context.data if isinstance(context.data, dict) else {},
                ),
                suggestions=[item.prompt for item in presets.presets[:3]],
                action=response_action,
            )
        if (
            pre_inferred_action is None
            and self._is_unmatched_text_entry_context(
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
                module_code=context.module_code,
            )
        ):
            reply = self._build_unmatched_text_entry_reply()
            assistant_message = AssistantMessage(
                tenant_id=tenant_id,
                session_id=session.id,
                role=MessageRole.ASSISTANT.value,
                content=reply,
                action_type="chat_reply",
                action_result={
                    "moduleCode": context.module_code,
                    "routePath": context.route_path,
                    "usedAi": planner_used_ai,
                    "assistantAction": None,
                    "actionExecution": None,
                    "boundary": "unmatched_text_entry",
                    "billing": self._merge_billing_payloads(planner_billing_payload),
                    "plannerBilling": planner_billing_payload,
                },
            )
            self.db.add(assistant_message)
            session.module_code = context.module_code
            session.route_path = self._session_route_after_turn(
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
            )
            session.context_data = self._build_persisted_session_context(
                context_params=bound_context_params,
                session_context=dict(session.context_data or {}) if isinstance(session.context_data, dict) else {},
                module_code=context.module_code,
                module_name=context.module_name,
                route_path=context.route_path,
                user_message=normalized_message,
                assistant_reply=reply,
                assistant_action=None,
            )
            await self.db.commit()
            return ChatReplyResponse(
                session_id=session.id,
                module_code=context.module_code,
                module_name=context.module_name,
                route_path=context.route_path,
                reply=reply,
                used_ai=planner_used_ai,
                context=self._response_context_for_entry(
                    entry_route_path=bound_route_path,
                    context_params=bound_context_params,
                    context_data=context.data if isinstance(context.data, dict) else {},
                ),
                suggestions=[item.prompt for item in presets.presets[:3]],
                action=None,
            )
        prompt_context = self._build_prompt_context_payload(
            adapter=adapter,
            module_code=context.module_code,
            module_name=context.module_name,
            route_path=context.route_path,
            context_data=context.data if isinstance(context.data, dict) else {},
            prior_action=prior_action,
        )
        prompt_stack = await self._resolve_prompt_stack(
            tenant_id=tenant_id,
            module_code=context.module_code,
            module_name=context.module_name,
            default_module_chat_prompt=getattr(adapter, "default_chat_prompt", None),
        )
        capability_context = build_assistant_capability_context(
            capability_config=capability_config,
            module_code=context.module_code,
            route_path=context.route_path,
            context_data=context.data,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
        )
        system_prompt = self._build_system_prompt(
            system_prompt=prompt_stack["system"],
            module_prompt=prompt_stack["moduleChat"],
            write_guard_prompt=prompt_stack["writeGuard"],
            module_name=context.module_name,
            route_path=context.route_path,
            prompt_context=prompt_context,
            capability_context_text=build_assistant_capability_context_text(capability_context),
            prior_action=prior_action,
            prior_execution=self._extract_prior_execution_summary(prior_action),
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(
            await self._build_chat_messages(
                session_id=session.id,
                session_context=bound_context_params,
                active_module_code=context.module_code,
                active_route_path=context.route_path,
            )
        )

        account_id = None
        reply = ""
        used_ai = False
        usage: dict[str, int] = {}
        assistant_action: dict[str, Any] | None = None
        if provider_settings:
            account_id = await ensure_credit_precheck(
                credit_service=self.credit_service,
                tenant_id=tenant_id,
                user_id=user_id,
                policy=billing_policy,
            )
            reply, used_ai, usage = await self._call_ai_reply(
                tenant_id=tenant_id,
                messages=messages,
                provider_settings=provider_settings,
            )
            reply, assistant_action = self._extract_reply_payload(reply)
        inferred_action = pre_inferred_action
        if reply and not provider_settings:
            post_model_inferred_action = await self._infer_best_adapter_action(
                route_path=context.route_path,
                user_message=normalized_message,
                reply_text=reply,
                context_params=bound_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=normalized_read_team_ids,
                prior_action=prior_action,
            )
            inferred_action = self._prefer_refined_action(pre_inferred_action, post_model_inferred_action)
        elif inferred_action is None and not provider_settings:
            inferred_action = await self._infer_best_adapter_action(
                route_path=context.route_path,
                user_message=normalized_message,
                reply_text="",
                context_params=bound_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=normalized_read_team_ids,
                prior_action=prior_action,
            )
        raw_action_context = None
        if assistant_action or inferred_action:
            raw_action_context = await self._load_action_guard_context(
                adapter=self._resolve_adapter(context.route_path),
                route_path=context.route_path,
                context_params=bound_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=normalized_read_team_ids,
            )
        assistant_action = await self._select_canonical_assistant_action(
            route_path=context.route_path,
            module_code=context.module_code,
            extracted_action=assistant_action,
            inferred_action=inferred_action,
            context_params=bound_context_params,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
            action_context_data=raw_action_context,
            capability_config=capability_config,
            prior_action=prior_action,
        )
        assistant_action = self._align_navigation_action_with_effective_route(
            assistant_action,
            entry_route_path=bound_route_path,
            effective_route_path=context.route_path,
            context_params=bound_context_params,
        )
        ai_completion_text = reply
        action_execution = await self._execute_auto_chat_action(
            adapter=adapter,
            assistant_action=assistant_action,
            route_path=context.route_path,
            context_params=bound_context_params,
            action_context_data=raw_action_context,
            capability_config=capability_config,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
        )
        if action_execution is not None:
            reply = str(action_execution.get("message") or "").strip() or reply
        billing = None
        reply_billing_payload = None
        if used_ai:
            billing = await charge_credits_by_usage(
                credit_service=self.credit_service,
                tenant_id=tenant_id,
                user_id=user_id,
                policy=billing_policy,
                account_id=account_id,
                reference_type="assistant_chat",
                reference_id=session.id,
                idempotency_key=(f"assistant_chat:{int(user_message.id)}" if user_message.id is not None else None),
                remark="AI 助手对话消耗",
                prompt_text=build_prompt_text_from_messages(messages),
                completion_text=ai_completion_text,
                usage=usage,
                extra={
                    "module_code": context.module_code,
                    "route_path": context.route_path,
                    "session_id": session.id,
                },
            )
            reply_billing_payload = build_billing_result_payload(billing, enabled=billing_policy.enabled)
            reply_billing_payload["providerCalls"] = 1
            reply_billing_payload["billingSource"] = "assistant_reply"
            reply_billing_payload["referenceType"] = "assistant_chat"
        if not reply:
            if assistant_action and assistant_action.get("summary"):
                reply = str(assistant_action["summary"]).strip()
            else:
                preset_prompts = [item.prompt for item in presets.presets]
                reply = self._build_fallback_reply(context.module_name, preset_prompts)
                assistant_action = None
        response_used_ai = bool(used_ai or planner_used_ai)
        total_billing_payload = self._merge_billing_payloads(planner_billing_payload, reply_billing_payload)

        assistant_message = AssistantMessage(
            tenant_id=tenant_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT.value,
            content=reply,
            action_type="chat_reply",
            action_result={
                "moduleCode": context.module_code,
                "routePath": context.route_path,
                "usedAi": response_used_ai,
                "assistantAction": assistant_action,
                "actionExecution": action_execution,
                "billing": total_billing_payload or build_billing_result_payload(None, enabled=billing_policy.enabled),
                "plannerBilling": planner_billing_payload,
                "replyBilling": reply_billing_payload,
            },
        )
        self.db.add(assistant_message)
        session.module_code = context.module_code
        session.route_path = self._session_route_after_turn(
            entry_route_path=bound_route_path,
            effective_route_path=context.route_path,
            context_params=bound_context_params,
        )
        session.context_data = self._build_persisted_session_context(
            context_params=bound_context_params,
            session_context=dict(session.context_data or {}) if isinstance(session.context_data, dict) else {},
            module_code=context.module_code,
            module_name=context.module_name,
            route_path=context.route_path,
            user_message=normalized_message,
            assistant_reply=reply,
            assistant_action=assistant_action,
        )
        await self.db.commit()

        response_action = self._response_action_for_entry(
            action=assistant_action,
            context_params=bound_context_params,
            action_execution=action_execution,
        )
        return ChatReplyResponse(
            session_id=session.id,
            module_code=context.module_code,
            module_name=context.module_name,
            route_path=context.route_path,
            reply=reply,
            used_ai=response_used_ai,
            context=self._response_context_for_entry(
                entry_route_path=bound_route_path,
                context_params=bound_context_params,
                context_data=context.data if isinstance(context.data, dict) else {},
            ),
            suggestions=[item.prompt for item in presets.presets[:3]],
            action=response_action,
        )

    async def execute_action(
        self,
        *,
        session_id: int,
        action_type: str,
        params: dict[str, Any] | None,
        tenant_id: int,
        user_id: int,
        team_ids: list[int] | None = None,
    ) -> ActionResponse:
        from app.domain.assistant.config_service import AssistantConfigService

        config_service = AssistantConfigService(self.db)
        await config_service.ensure_enabled(tenant_id)
        assistant_config = None
        if callable(getattr(self.db, "execute", None)):
            assistant_config = await config_service.get_config(tenant_id)
        session = await self.get_session(session_id=session_id, tenant_id=tenant_id, user_id=user_id)
        viewer_team_ids = await self._get_user_team_ids(tenant_id, user_id)
        normalized_read_team_ids = self._derive_team_ids(team_ids)
        capability_config = self._extract_capability_config(assistant_config)
        normalized_params = dict(params or {})
        bound_route_path = _normalize_route_path(session.route_path)
        session_context_data = (
            dict(getattr(session, "context_data", {}) or {})
            if isinstance(getattr(session, "context_data", {}) or {}, dict)
            else {}
        )
        routing = session_context_data.get(routing_state_key())
        active_route_path = (
            _normalize_route_path(routing.get("activeRoutePath"))
            if isinstance(routing, dict) and routing.get("activeRoutePath")
            else ""
        )
        requested_route_path = _normalize_route_path(
            normalized_params.get("targetRoutePath")
            or normalized_params.get("target_route_path")
            or normalized_params.get("routePath")
            or normalized_params.get("route_path")
            or ""
        )
        if (
            action_type != "page.router.navigate"
            and is_text_entry_route(bound_route_path, session_context_data)
            and active_route_path not in {"", "/", "/assistant", _MESSAGE_CHANNEL_ROUTE}
        ):
            effective_action_route_path = requested_route_path if requested_route_path != "/" else active_route_path
        else:
            effective_action_route_path = requested_route_path if requested_route_path != "/" else bound_route_path
        adapter = self._resolve_adapter(effective_action_route_path)
        normalized_params["routePath"] = effective_action_route_path
        normalized_params["route_path"] = effective_action_route_path
        normalized_params["entryRoutePath"] = bound_route_path
        normalized_params.setdefault("contextParams", dict(session_context_data))
        normalized_params.setdefault("context_params", dict(session_context_data))

        raw_action_context = await self._load_action_guard_context(
            adapter=adapter,
            route_path=effective_action_route_path,
            context_params=session_context_data,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
        )
        result = await self._execute_action_runtime(
            adapter=adapter,
            action_type=action_type,
            params=normalized_params,
            route_path=effective_action_route_path,
            context_params=session_context_data,
            action_context_data=raw_action_context,
            capability_config=capability_config,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
        )

        message = str(result.message or "").strip() or ("操作执行成功" if result.success else "操作执行失败")
        self.db.add(
            AssistantMessage(
                tenant_id=tenant_id,
                session_id=session.id,
                role=MessageRole.ASSISTANT.value,
                content=message,
                action_type=action_type,
                action_result={
                    "moduleCode": adapter.module_code,
                    "routePath": effective_action_route_path,
                    "entryRoutePath": bound_route_path,
                    "success": bool(result.success),
                    "data": result.data or {},
                    "actionExecution": {
                        "actionType": action_type,
                        "success": bool(result.success),
                        "message": message,
                        "result": result.data or {},
                    },
                },
            )
        )
        await self.db.commit()

        return ActionResponse(
            success=bool(result.success),
            action_type=action_type,
            result=result.data,
            message=message,
        )

    @collects_usage("assistant:chat_stream")
    async def chat_stream(
        self,
        session_id: int,
        message: str,
        tenant_id: int,
        user_id: int,
        team_ids: list[int] | None = None,
        route_path: str | None = None,
        context_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        from app.domain.assistant.config_service import AssistantConfigService

        config_service = AssistantConfigService(self.db)
        await config_service.ensure_enabled(tenant_id)
        assistant_config = await config_service.get_config(tenant_id)
        session = await self.get_session(session_id=session_id, tenant_id=tenant_id, user_id=user_id)
        bound_route_path = _normalize_route_path(route_path or session.route_path)
        bound_context_params = (
            dict(context_params)
            if isinstance(context_params, dict)
            else dict(session.context_data or {}) if isinstance(session.context_data, dict) else {}
        )

        normalized_message = str(message or "").strip()
        if not normalized_message:
            yield json.dumps({"type": "error", "content": "请输入消息内容"})
            return

        provider_settings = await config_service.get_provider_settings(tenant_id)
        billing_policy = self._build_billing_policy_from_config(assistant_config)
        user_message = AssistantMessage(
            tenant_id=tenant_id,
            session_id=session.id,
            role=MessageRole.USER.value,
            content=normalized_message,
        )
        self.db.add(user_message)
        flush = getattr(self.db, "flush", None)
        if callable(flush):
            result = flush()
            if inspect.isawaitable(result):
                await result
        effective_route_path, bound_context_params = await self._resolve_effective_turn_route(
            session=session,
            message=normalized_message,
            bound_route_path=bound_route_path,
            bound_context_params=bound_context_params,
            tenant_id=tenant_id,
            user_id=user_id,
            provider_settings=provider_settings,
            billing_policy=billing_policy,
            user_message_id=user_message.id,
        )
        await self.db.commit()

        context = await self.get_context(
            tenant_id=tenant_id,
            user_id=user_id,
            route_path=effective_route_path,
            context_params=bound_context_params,
            team_ids=team_ids,
        )
        if isinstance(context.data, dict):
            context.data = self._attach_foundation_context(
                context_data=context.data,
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
            )
        user_message.action_result = {
            "moduleCode": context.module_code,
            "routePath": context.route_path,
            "entryRoutePath": bound_route_path,
        }
        viewer_team_ids = await self._get_user_team_ids(tenant_id, user_id)
        normalized_read_team_ids = self._derive_team_ids(team_ids)
        presets = await self.get_presets(
            tenant_id=tenant_id,
            user_id=user_id,
            route_path=effective_route_path,
            context_params=bound_context_params,
            team_ids=team_ids,
        )
        adapter = self._resolve_adapter(context.route_path)
        prior_action = await self._get_last_assistant_action(
            session_id=session.id,
            module_code=context.module_code,
            route_path=context.route_path,
        )
        planner_used_ai = self._routing_used_ai(bound_context_params)
        planner_billing_payload = self._planner_billing_payload(bound_context_params)
        capability_config = self._extract_capability_config(assistant_config)
        if provider_settings:
            pre_inferred_action = self._planned_action_from_routing_state(
                context_params=bound_context_params,
                context_data=context.data if isinstance(context.data, dict) else {},
            )
        else:
            pre_inferred_action = await self._infer_best_adapter_action(
                route_path=context.route_path,
                user_message=normalized_message,
                reply_text="",
                context_params=bound_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=normalized_read_team_ids,
                prior_action=prior_action,
            )
            if pre_inferred_action is None:
                pre_inferred_action = self._planned_action_from_routing_state(
                    context_params=bound_context_params,
                    context_data=context.data if isinstance(context.data, dict) else {},
                )
        blocked_action_reply = self._preplanned_action_blocked_reply(
            action=pre_inferred_action,
            module_code=context.module_code,
            context_data=context.data if isinstance(context.data, dict) else {},
            capability_config=capability_config,
            builtin_tool_ids=self._assistant_builtin_tool_ids(),
        )
        if blocked_action_reply:
            yield json.dumps({"type": "content", "content": blocked_action_reply})
            self.db.add(
                AssistantMessage(
                    tenant_id=tenant_id,
                    session_id=session.id,
                    role=MessageRole.ASSISTANT.value,
                    content=blocked_action_reply,
                    action_type="chat_stream",
                    action_result={
                        "moduleCode": context.module_code,
                        "routePath": context.route_path,
                        "usedAi": planner_used_ai,
                        "assistantAction": None,
                        "actionExecution": None,
                        "boundary": "action_unavailable",
                        "billing": self._merge_billing_payloads(planner_billing_payload),
                        "plannerBilling": planner_billing_payload,
                    },
                )
            )
            session.module_code = context.module_code
            session.route_path = self._session_route_after_turn(
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
            )
            session.context_data = self._build_persisted_session_context(
                context_params=bound_context_params,
                session_context=dict(session.context_data or {}) if isinstance(session.context_data, dict) else {},
                module_code=context.module_code,
                module_name=context.module_name,
                route_path=context.route_path,
                user_message=normalized_message,
                assistant_reply=blocked_action_reply,
                assistant_action=None,
            )
            await self.db.commit()
            yield json.dumps(
                {
                    "type": "done",
                    "reply": blocked_action_reply,
                    "usedAi": planner_used_ai,
                    "moduleCode": context.module_code,
                    "moduleName": context.module_name,
                    "routePath": context.route_path,
                    "context": self._response_context_for_entry(
                        entry_route_path=bound_route_path,
                        context_params=bound_context_params,
                        context_data=context.data if isinstance(context.data, dict) else {},
                    ),
                    "suggestions": [item.prompt for item in presets.presets[:3]],
                    "action": None,
                }
            )
            return
        pre_auto_action_context = context.data if isinstance(context.data, dict) else {}
        pre_auto_action = await self._select_canonical_assistant_action(
            route_path=context.route_path,
            module_code=context.module_code,
            extracted_action=None,
            inferred_action=pre_inferred_action,
            context_params=bound_context_params,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
            action_context_data=pre_auto_action_context,
            capability_config=capability_config,
            prior_action=prior_action,
        )
        pre_auto_action = self._align_navigation_action_with_effective_route(
            pre_auto_action,
            entry_route_path=bound_route_path,
            effective_route_path=context.route_path,
            context_params=bound_context_params,
        )
        pre_action_execution = await self._execute_auto_chat_action(
            adapter=adapter,
            assistant_action=pre_auto_action,
            route_path=context.route_path,
            context_params=bound_context_params,
            action_context_data=pre_auto_action_context,
            capability_config=capability_config,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
        )
        if pre_action_execution is not None:
            reply = str(pre_action_execution.get("message") or "").strip() or "查询已完成。"
            yield json.dumps({"type": "content", "content": reply})
            self.db.add(
                AssistantMessage(
                    tenant_id=tenant_id,
                    session_id=session.id,
                    role=MessageRole.ASSISTANT.value,
                    content=reply,
                    action_type="chat_stream",
                    action_result={
                        "moduleCode": context.module_code,
                        "routePath": context.route_path,
                        "usedAi": planner_used_ai,
                        "assistantAction": pre_auto_action,
                        "actionExecution": pre_action_execution,
                        "boundary": "auto_read_tool",
                        "billing": self._merge_billing_payloads(planner_billing_payload),
                        "plannerBilling": planner_billing_payload,
                    },
                )
            )
            session.module_code = context.module_code
            session.route_path = self._session_route_after_turn(
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
            )
            session.context_data = self._build_persisted_session_context(
                context_params=bound_context_params,
                session_context=dict(session.context_data or {}) if isinstance(session.context_data, dict) else {},
                module_code=context.module_code,
                module_name=context.module_name,
                route_path=context.route_path,
                user_message=normalized_message,
                assistant_reply=reply,
                assistant_action=pre_auto_action,
            )
            await self.db.commit()
            response_action = self._response_action_for_entry(
                action=pre_auto_action,
                context_params=bound_context_params,
                action_execution=pre_action_execution,
            )
            yield json.dumps(
                {
                    "type": "done",
                    "reply": reply,
                    "usedAi": planner_used_ai,
                    "moduleCode": context.module_code,
                    "moduleName": context.module_name,
                    "routePath": context.route_path,
                    "context": self._response_context_for_entry(
                        entry_route_path=bound_route_path,
                        context_params=bound_context_params,
                        context_data=context.data if isinstance(context.data, dict) else {},
                    ),
                    "suggestions": [item.prompt for item in presets.presets[:3]],
                    "action": response_action,
                }
            )
            return
        if (
            pre_inferred_action is None
            and self._is_unmatched_text_entry_context(
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
                module_code=context.module_code,
            )
        ):
            reply = self._build_unmatched_text_entry_reply()
            yield json.dumps({"type": "content", "content": reply})
            self.db.add(
                AssistantMessage(
                    tenant_id=tenant_id,
                    session_id=session.id,
                    role=MessageRole.ASSISTANT.value,
                    content=reply,
                    action_type="chat_stream",
                    action_result={
                        "moduleCode": context.module_code,
                        "routePath": context.route_path,
                        "usedAi": planner_used_ai,
                        "assistantAction": None,
                        "actionExecution": None,
                        "boundary": "unmatched_text_entry",
                        "billing": self._merge_billing_payloads(planner_billing_payload),
                        "plannerBilling": planner_billing_payload,
                    },
                )
            )
            session.module_code = context.module_code
            session.route_path = self._session_route_after_turn(
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
            )
            session.context_data = self._build_persisted_session_context(
                context_params=bound_context_params,
                session_context=dict(session.context_data or {}) if isinstance(session.context_data, dict) else {},
                module_code=context.module_code,
                module_name=context.module_name,
                route_path=context.route_path,
                user_message=normalized_message,
                assistant_reply=reply,
                assistant_action=None,
            )
            await self.db.commit()
            yield json.dumps(
                {
                    "type": "done",
                    "reply": reply,
                    "usedAi": planner_used_ai,
                    "context": self._response_context_for_entry(
                        entry_route_path=bound_route_path,
                        context_params=bound_context_params,
                        context_data=context.data if isinstance(context.data, dict) else {},
                    ),
                    "suggestions": [item.prompt for item in presets.presets[:3]],
                    "action": None,
                    "moduleCode": context.module_code,
                    "moduleName": context.module_name,
                    "routePath": context.route_path,
                }
            )
            return
        prompt_context = self._build_prompt_context_payload(
            adapter=adapter,
            module_code=context.module_code,
            module_name=context.module_name,
            route_path=context.route_path,
            context_data=context.data if isinstance(context.data, dict) else {},
            prior_action=prior_action,
        )
        prompt_stack = await self._resolve_prompt_stack(
            tenant_id=tenant_id,
            module_code=context.module_code,
            module_name=context.module_name,
            default_module_chat_prompt=getattr(adapter, "default_chat_prompt", None),
        )
        capability_context = build_assistant_capability_context(
            capability_config=capability_config,
            module_code=context.module_code,
            route_path=context.route_path,
            context_data=context.data,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
        )
        system_prompt = self._build_system_prompt(
            system_prompt=prompt_stack["system"],
            module_prompt=prompt_stack["moduleChat"],
            write_guard_prompt=prompt_stack["writeGuard"],
            module_name=context.module_name,
            route_path=context.route_path,
            prompt_context=prompt_context,
            capability_context_text=build_assistant_capability_context_text(capability_context),
            prior_action=prior_action,
            prior_execution=self._extract_prior_execution_summary(prior_action),
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(
            await self._build_chat_messages(
                session_id=session.id,
                session_context=bound_context_params,
                active_module_code=context.module_code,
                active_route_path=context.route_path,
            )
        )

        if not provider_settings:
            inferred_action = pre_inferred_action
            raw_action_context = None
            if inferred_action:
                raw_action_context = await self._load_action_guard_context(
                    adapter=adapter,
                    route_path=context.route_path,
                    context_params=bound_context_params,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    viewer_team_ids=viewer_team_ids,
                    read_team_ids=normalized_read_team_ids,
                )
            assistant_action = await self._select_canonical_assistant_action(
                route_path=context.route_path,
                module_code=context.module_code,
                extracted_action=None,
                inferred_action=inferred_action,
                context_params=bound_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=normalized_read_team_ids,
                action_context_data=raw_action_context,
                capability_config=capability_config,
                prior_action=prior_action,
            )
            assistant_action = self._align_navigation_action_with_effective_route(
                assistant_action,
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
            )
            action_execution = await self._execute_auto_chat_action(
                adapter=adapter,
                assistant_action=assistant_action,
                route_path=context.route_path,
                context_params=bound_context_params,
                action_context_data=raw_action_context,
                capability_config=capability_config,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=normalized_read_team_ids,
            )
            fallback = (
                str(action_execution.get("message") or "").strip()
                if action_execution is not None
                else self._build_fallback_reply(context.module_name, [item.prompt for item in presets.presets])
            )
            suggestions = [item.prompt for item in presets.presets[:3]]
            yield json.dumps({"type": "content", "content": fallback})
            self.db.add(
                AssistantMessage(
                    tenant_id=tenant_id,
                    session_id=session.id,
                    role=MessageRole.ASSISTANT.value,
                    content=fallback,
                    action_type="chat_stream",
                    action_result={
                        "moduleCode": context.module_code,
                        "routePath": context.route_path,
                        "usedAi": False,
                        "assistantAction": assistant_action,
                        "actionExecution": action_execution,
                    },
                )
            )
            session.module_code = context.module_code
            session.route_path = self._session_route_after_turn(
                entry_route_path=bound_route_path,
                effective_route_path=context.route_path,
                context_params=bound_context_params,
            )
            session.context_data = self._build_persisted_session_context(
                context_params=bound_context_params,
                session_context=dict(session.context_data or {}) if isinstance(session.context_data, dict) else {},
                module_code=context.module_code,
                module_name=context.module_name,
                route_path=context.route_path,
                user_message=normalized_message,
                assistant_reply=fallback,
                assistant_action=assistant_action,
            )
            await self.db.commit()
            yield json.dumps(
                {
                    "type": "done",
                    "reply": fallback,
                    "usedAi": False,
                    "moduleCode": context.module_code,
                    "moduleName": context.module_name,
                    "routePath": context.route_path,
                    "context": self._response_context_for_entry(
                        entry_route_path=bound_route_path,
                        context_params=bound_context_params,
                        context_data=context.data if isinstance(context.data, dict) else {},
                    ),
                    "suggestions": suggestions,
                    "action": self._response_action_for_entry(
                        action=assistant_action,
                        context_params=bound_context_params,
                        action_execution=action_execution,
                    ),
                }
            )
            return

        account_id = await ensure_credit_precheck(
            credit_service=self.credit_service,
            tenant_id=tenant_id,
            user_id=user_id,
            policy=billing_policy,
        )

        client = self._build_ai_client(provider_settings)

        full_response = ""
        streamed_visible_response = ""
        used_ai = False
        usage_payload: dict[str, int] = {}
        billing = None
        reply_billing_payload = None
        assistant_action: dict[str, Any] | None = None
        if provider_settings.get("stream", True):
            try:
                async for chunk in client.chat_stream(messages):
                    full_response += chunk
                    next_visible_response = sanitize_streaming_assistant_text(full_response)
                    if len(next_visible_response) < len(streamed_visible_response):
                        continue
                    next_delta = next_visible_response[len(streamed_visible_response):]
                    streamed_visible_response = next_visible_response
                    if next_delta:
                        yield json.dumps({"type": "content", "content": next_delta})
            except Exception as exc:
                logger.warning(
                    "assistant_chat_stream_failed",
                    tenant_id=tenant_id,
                    user_id=user_id,
                    session_id=session.id,
                    route_path=context.route_path,
                    partial_chars=len(full_response),
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                full_response, _, usage_payload = await self._call_ai_reply(
                    tenant_id=tenant_id,
                    messages=messages,
                    provider_settings=provider_settings,
                )
                full_response = str(full_response or "")
                next_visible_response = sanitize_streaming_assistant_text(full_response)
                if next_visible_response and next_visible_response.startswith(streamed_visible_response):
                    next_delta = next_visible_response[len(streamed_visible_response):]
                    streamed_visible_response = next_visible_response
                    if next_delta:
                        yield json.dumps({"type": "content", "content": next_delta})
        else:
            full_response, _, usage_payload = await self._call_ai_reply(
                tenant_id=tenant_id,
                messages=messages,
                provider_settings=provider_settings,
            )
            full_response = str(full_response or "")
            streamed_visible_response = sanitize_streaming_assistant_text(full_response)
            if streamed_visible_response:
                yield json.dumps({"type": "content", "content": streamed_visible_response})

        full_response, assistant_action = self._extract_reply_payload(full_response)
        used_ai = bool(full_response.strip() or assistant_action)
        inferred_action = pre_inferred_action
        if full_response and not provider_settings:
            post_model_inferred_action = await self._infer_best_adapter_action(
                route_path=context.route_path,
                user_message=normalized_message,
                reply_text=full_response,
                context_params=bound_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=normalized_read_team_ids,
                prior_action=prior_action,
            )
            inferred_action = self._prefer_refined_action(pre_inferred_action, post_model_inferred_action)
        elif inferred_action is None and not provider_settings:
            inferred_action = await self._infer_best_adapter_action(
                route_path=context.route_path,
                user_message=normalized_message,
                reply_text="",
                context_params=bound_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=normalized_read_team_ids,
                prior_action=prior_action,
            )
        raw_action_context = None
        if assistant_action or inferred_action:
            raw_action_context = await self._load_action_guard_context(
                adapter=self._resolve_adapter(context.route_path),
                route_path=context.route_path,
                context_params=bound_context_params,
                tenant_id=tenant_id,
                user_id=user_id,
                viewer_team_ids=viewer_team_ids,
                read_team_ids=normalized_read_team_ids,
            )
        assistant_action = await self._select_canonical_assistant_action(
            route_path=context.route_path,
            module_code=context.module_code,
            extracted_action=assistant_action,
            inferred_action=inferred_action,
            context_params=bound_context_params,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
            action_context_data=raw_action_context,
            capability_config=capability_config,
            prior_action=prior_action,
        )
        assistant_action = self._align_navigation_action_with_effective_route(
            assistant_action,
            entry_route_path=bound_route_path,
            effective_route_path=context.route_path,
            context_params=bound_context_params,
        )
        ai_completion_text = full_response
        action_execution = await self._execute_auto_chat_action(
            adapter=adapter,
            assistant_action=assistant_action,
            route_path=context.route_path,
            context_params=bound_context_params,
            action_context_data=raw_action_context,
            capability_config=capability_config,
            tenant_id=tenant_id,
            user_id=user_id,
            viewer_team_ids=viewer_team_ids,
            read_team_ids=normalized_read_team_ids,
        )
        if action_execution is not None:
            execution_reply = str(action_execution.get("message") or "").strip()
            if execution_reply:
                if execution_reply != full_response.strip():
                    separator = "\n\n" if streamed_visible_response else ""
                    yield json.dumps({"type": "content", "content": f"{separator}{execution_reply}"})
                full_response = execution_reply
        if not used_ai and action_execution is None:
            if assistant_action and assistant_action.get("summary"):
                full_response = str(assistant_action["summary"]).strip()
                yield json.dumps({"type": "content", "content": full_response})
            else:
                full_response = self._build_fallback_reply(context.module_name, [item.prompt for item in presets.presets])
                yield json.dumps({"type": "content", "content": full_response})
                assistant_action = None
        elif used_ai:
            try:
                billing = await charge_credits_by_usage(
                    credit_service=self.credit_service,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    policy=billing_policy,
                    account_id=account_id,
                    reference_type="assistant_chat",
                    reference_id=session.id,
                    idempotency_key=(f"assistant_chat:{int(user_message.id)}" if user_message.id is not None else None),
                    remark="AI 助手流式对话消耗",
                    prompt_text=build_prompt_text_from_messages(messages),
                    completion_text=ai_completion_text,
                    usage=usage_payload,
                    extra={
                        "module_code": context.module_code,
                        "route_path": context.route_path,
                        "session_id": session.id,
                        "stream": bool(provider_settings.get("stream", True)),
                    },
                )
                reply_billing_payload = build_billing_result_payload(billing, enabled=billing_policy.enabled)
                reply_billing_payload["providerCalls"] = 1
                reply_billing_payload["billingSource"] = "assistant_reply"
                reply_billing_payload["referenceType"] = "assistant_chat"
            except Exception as exc:
                logger.warning(
                    "assistant_chat_stream_billing_failed",
                    tenant_id=tenant_id,
                    user_id=user_id,
                    session_id=session.id,
                    route_path=context.route_path,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )

        response_used_ai = bool(used_ai or planner_used_ai)
        total_billing_payload = self._merge_billing_payloads(planner_billing_payload, reply_billing_payload)
        self.db.add(
            AssistantMessage(
                tenant_id=tenant_id,
                session_id=session.id,
                role=MessageRole.ASSISTANT.value,
                content=full_response,
                action_type="chat_stream",
                action_result={
                    "moduleCode": context.module_code,
                    "routePath": context.route_path,
                    "usedAi": response_used_ai,
                    "assistantAction": assistant_action,
                    "actionExecution": action_execution,
                    "billing": total_billing_payload or build_billing_result_payload(None, enabled=billing_policy.enabled),
                    "plannerBilling": planner_billing_payload,
                    "replyBilling": reply_billing_payload,
                },
            )
        )
        session.module_code = context.module_code
        session.route_path = self._session_route_after_turn(
            entry_route_path=bound_route_path,
            effective_route_path=context.route_path,
            context_params=bound_context_params,
        )
        session.context_data = self._build_persisted_session_context(
            context_params=bound_context_params,
            session_context=dict(session.context_data or {}) if isinstance(session.context_data, dict) else {},
            module_code=context.module_code,
            module_name=context.module_name,
            route_path=context.route_path,
            user_message=normalized_message,
            assistant_reply=full_response,
            assistant_action=assistant_action,
        )
        await self.db.commit()
        response_action = self._response_action_for_entry(
            action=assistant_action,
            context_params=bound_context_params,
            action_execution=action_execution,
        )
        yield json.dumps(
            {
                "type": "done",
                "reply": full_response,
                "usedAi": response_used_ai,
                "moduleCode": context.module_code,
                "moduleName": context.module_name,
                "routePath": context.route_path,
                "context": self._response_context_for_entry(
                    entry_route_path=bound_route_path,
                    context_params=bound_context_params,
                    context_data=context.data if isinstance(context.data, dict) else {},
                ),
                "suggestions": [item.prompt for item in presets.presets[:3]],
                "action": response_action,
            }
        )
