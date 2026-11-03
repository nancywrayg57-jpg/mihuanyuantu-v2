from app.api.v1.endpoints.menus import MenuItem, MenuTreeItem
from app.api.v1.endpoints.site import SitePublicConfig
from app.api.v1.endpoints.tenant_profile import TenantSettingsUpdate
from app.domain.speech.schemas import SpeechTenantConfigUpsertRequest


def test_menu_item_model_dump_keeps_camel_case_aliases() -> None:
    item = MenuItem.model_validate(
        {
            "id": 1,
            "title": "系统管理",
            "parent_id": 9,
            "sort_order": 3,
            "menu_type": "1",
            "is_visible": True,
            "is_cache": False,
            "is_frame": False,
            "frame_src": None,
            "is_active": True,
            "no_cache": False,
            "no_tags_view": False,
            "can_to": False,
            "always_show": True,
            "created_at": "2026-03-21T00:00:00Z",
            "updated_at": "2026-03-21T00:00:00Z",
        }
    )

    dumped = item.model_dump(by_alias=True)

    assert dumped["parentId"] == 9
    assert dumped["sortOrder"] == 3
    assert dumped["menuType"] == "1"
    assert dumped["isVisible"] is True
    assert dumped["createdAt"] == "2026-03-21T00:00:00Z"
    assert dumped["updatedAt"] == "2026-03-21T00:00:00Z"
    assert "parent_id" not in dumped


def test_menu_tree_item_accepts_alias_and_field_name_recursively() -> None:
    tree = MenuTreeItem.model_validate(
        {
            "value": 1,
            "label": "系统管理",
            "sortOrder": 10,
            "children": [
                {
                    "value": 2,
                    "label": "菜单管理",
                    "order": 5,
                }
            ],
        }
    )

    dumped = tree.model_dump(by_alias=True)

    assert tree.order == 10
    assert tree.children[0].order == 5
    assert dumped["sortOrder"] == 10
    assert dumped["children"][0]["sortOrder"] == 5


def test_site_public_config_dumps_public_camel_case_contract() -> None:
    config = SitePublicConfig.model_validate(
        {
            "tenant_id": 7,
            "tenant_code": "demo",
            "tenant_name": "演示租户",
            "seo": {
                "title": "AOJUAI",
                "keywords": "ai,tenant",
                "description": "demo",
            },
        }
    )

    dumped = config.model_dump(by_alias=True)

    assert dumped["tenantId"] == 7
    assert dumped["tenantCode"] == "demo"
    assert dumped["tenantName"] == "演示租户"
    assert dumped["seo"]["title"] == "AOJUAI"


def test_speech_upsert_payload_accepts_camel_case_nested_fields() -> None:
    payload = SpeechTenantConfigUpsertRequest.model_validate(
        {
            "isActive": False,
            "tts": {
                "providerId": "edge_tts",
                "settings": {"voice": "zh-CN-XiaoxiaoNeural"},
                "secrets": {"apiKey": "hidden"},
            },
            "stt": {
                "providerId": "browser",
                "settings": {"language": "zh-CN"},
            },
            "bargeIn": {
                "enabled": True,
                "stopWords": ["停止"],
                "wakeWords": ["你好助手"],
            },
        }
    )

    assert payload.enabled is False
    assert payload.tts is not None
    assert payload.tts.provider_id == "edge_tts"
    assert payload.tts.settings == {"voice": "zh-CN-XiaoxiaoNeural"}
    assert payload.stt is not None
    assert payload.stt.provider_id == "browser"
    assert payload.barge_in is not None
    assert payload.barge_in.stop_words == ["停止"]
    assert payload.barge_in.wake_words == ["你好助手"]


def test_speech_upsert_payload_accepts_snake_case_and_dumps_aliases() -> None:
    payload = SpeechTenantConfigUpsertRequest.model_validate(
        {
            "enabled": True,
            "tts": {
                "provider_id": "edge_tts",
                "settings": {"voice": "zh-CN-YunxiNeural"},
                "secrets": {"api_key": "hidden"},
            },
            "barge_in": {
                "enabled": False,
                "stop_words": ["暂停"],
            },
        }
    )

    dumped = payload.model_dump(by_alias=True, exclude_none=True)

    assert payload.tts is not None
    assert payload.tts.provider_id == "edge_tts"
    assert dumped["enabled"] is True
    assert dumped["tts"]["providerId"] == "edge_tts"
    assert dumped["bargeIn"]["enabled"] is False
    assert dumped["bargeIn"]["stopWords"] == ["暂停"]


def test_speech_upsert_payload_accepts_tts_profiles_aliases() -> None:
    payload = SpeechTenantConfigUpsertRequest.model_validate(
        {
            "ttsProfiles": [
                {
                    "id": "host-main",
                    "label": "默认主持人",
                    "providerId": "edge_tts",
                    "settings": {"voice": "zh-CN-XiaoxiaoNeural"},
                    "allowVoiceClone": True,
                    "isDefault": True,
                }
            ],
            "defaultTtsProfileId": "host-main",
        }
    )

    dumped = payload.model_dump(by_alias=True, exclude_none=True)

    assert payload.tts_profiles is not None
    assert payload.tts_profiles[0].provider_id == "edge_tts"
    assert payload.tts_profiles[0].allow_voice_clone is True
    assert payload.default_tts_profile_id == "host-main"
    assert dumped["ttsProfiles"][0]["allowVoiceClone"] is True
    assert dumped["defaultTtsProfileId"] == "host-main"


def test_tenant_settings_update_accepts_timezone_field() -> None:
    payload = TenantSettingsUpdate.model_validate(
        {
            "timezone": "Asia/Shanghai",
        }
    )

    assert payload.timezone == "Asia/Shanghai"
