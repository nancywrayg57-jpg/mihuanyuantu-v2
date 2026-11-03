from __future__ import annotations

from app.domain.menus.models import Menu
from app.domain.roles.models import DataRangeEnum


def test_roles_data_range_semantics_stay_kernel_compatible() -> None:
    assert int(DataRangeEnum.SELF) == 0
    assert int(DataRangeEnum.TEAM) == 1
    assert int(DataRangeEnum.DEPT) == 1
    assert int(DataRangeEnum.TEAM_BELOW) == 2
    assert int(DataRangeEnum.DEPT_BELOW) == 2
    assert int(DataRangeEnum.CUSTOM) == 3
    assert int(DataRangeEnum.ALL) == 4
    assert DataRangeEnum.DEPT is DataRangeEnum.TEAM
    assert DataRangeEnum.DEPT_BELOW is DataRangeEnum.TEAM_BELOW


def test_menu_route_contract_normalizes_dynamic_segments_and_column_meta_precedence() -> None:
    menu = Menu(
        title="Speech Provider",
        path="/speech/providers/:providerId",
        icon="ri/voiceprint-line",
        sort_order=7,
        is_visible=True,
        no_cache=False,
        breadcrumb=True,
        affix=False,
        no_tags_view=False,
        can_to=False,
        always_show=True,
        meta={
            "title": "Legacy Title",
            "icon": "legacy-icon",
            "rank": 99,
            "showLink": False,
            "hidden": True,
            "keepAlive": False,
            "noCache": True,
        },
    )

    route = menu.to_route_dict()

    assert route["name"] == "SpeechProvidersProviderId"
    assert route["meta"]["title"] == "Speech Provider"
    assert route["meta"]["icon"] == "ri/voiceprint-line"
    assert route["meta"]["rank"] == 7
    assert route["meta"]["showLink"] is True
    assert route["meta"]["hidden"] is False
    assert route["meta"]["keepAlive"] is True
    assert route["meta"]["noCache"] is False


def test_menu_route_contract_hides_legacy_speech_demo_entry() -> None:
    menu = Menu(
        title="Speech Demo",
        path="/system/speech/demo",
        is_visible=True,
        no_cache=False,
        breadcrumb=True,
        affix=False,
        no_tags_view=False,
        can_to=False,
        always_show=True,
        meta={},
    )

    route = menu.to_route_dict()

    assert route["meta"]["showLink"] is False
    assert route["meta"]["hidden"] is True
    assert route["meta"]["canTo"] is True
