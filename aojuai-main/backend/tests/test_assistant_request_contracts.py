from __future__ import annotations

from app.api.v1.endpoints.assistant import AssistantChatRequest
from app.domain.assistant.schemas import ChatReplyRequest, SessionCreate


def test_assistant_session_create_accepts_camel_and_snake_case() -> None:
    camel = SessionCreate.model_validate(
        {
            "routePath": "/dashboard",
            "contextParams": {"tab": "overview"},
        }
    )
    snake = SessionCreate.model_validate(
        {
            "route_path": "/dashboard",
            "context_params": {"tab": "overview"},
        }
    )

    assert camel.route_path == "/dashboard"
    assert camel.context_params == {"tab": "overview"}
    assert snake.route_path == camel.route_path
    assert snake.context_params == camel.context_params


def test_assistant_chat_requests_accept_route_and_context_aliases() -> None:
    sync_camel = ChatReplyRequest.model_validate(
        {
            "sessionId": 7,
            "message": "hello",
            "routePath": "/projects/detail/1",
            "contextParams": {"projectId": 1},
        }
    )
    sync_snake = ChatReplyRequest.model_validate(
        {
            "session_id": 7,
            "message": "hello",
            "route_path": "/projects/detail/1",
            "context_params": {"projectId": 1},
        }
    )
    stream_camel = AssistantChatRequest.model_validate(
        {
            "sessionId": 7,
            "message": "hello",
            "routePath": "/projects/detail/1",
            "contextParams": {"projectId": 1},
        }
    )
    stream_snake = AssistantChatRequest.model_validate(
        {
            "session_id": 7,
            "message": "hello",
            "route_path": "/projects/detail/1",
            "context_params": {"projectId": 1},
        }
    )

    assert sync_camel.route_path == "/projects/detail/1"
    assert sync_camel.context_params == {"projectId": 1}
    assert sync_snake.route_path == sync_camel.route_path
    assert sync_snake.context_params == sync_camel.context_params
    assert stream_camel.route_path == sync_camel.route_path
    assert stream_camel.context_params == sync_camel.context_params
    assert stream_snake.route_path == sync_camel.route_path
    assert stream_snake.context_params == sync_camel.context_params
