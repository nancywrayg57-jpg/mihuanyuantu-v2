from app.api.v1.endpoints.menus import build_menu_tree, build_route_tree


class DummyMenu:
    def __init__(
        self,
        *,
        menu_id: int,
        title: str,
        path: str | None,
        parent_id: int | None,
        menu_type: str,
        sort_order: int,
        meta: dict | None = None,
        component: str | None = None,
    ) -> None:
        self.id = menu_id
        self.title = title
        self.path = path
        self.parent_id = parent_id
        self.menu_type = menu_type
        self.sort_order = sort_order
        self.is_active = True
        self.deleted_at = None
        self.meta = meta or {}
        self.component = component
        self.always_show = False

    def to_route_dict(self, parent_name: str = "") -> dict:
        route_name = (self.path or f"menu-{self.id}").strip("/").replace("/", "-") or f"menu-{self.id}"
        return {
            "path": self.path,
            "name": route_name,
            "meta": {"title": self.title},
            "component": None,
        }


def test_build_route_tree_dedupes_duplicate_module_root_and_children() -> None:
    menus = [
        DummyMenu(menu_id=1, title="语音能力", path="/speech", parent_id=None, menu_type="0", sort_order=1),
        DummyMenu(menu_id=2, title="语音能力", path="/speech", parent_id=None, menu_type="0", sort_order=1),
        DummyMenu(menu_id=11, title="语音控制台", path="/speech/console", parent_id=1, menu_type="1", sort_order=1),
        DummyMenu(menu_id=21, title="语音控制台", path="/speech/console", parent_id=2, menu_type="1", sort_order=1),
    ]

    routes = build_route_tree(menus, user_menu_ids={2, 21}, is_superuser=False)

    assert len(routes) == 1
    assert routes[0]["path"] == "/speech"
    assert len(routes[0].get("children", [])) == 1
    assert routes[0]["children"][0]["path"] == "/speech/console"


def test_build_menu_tree_keeps_distinct_button_items() -> None:
    menus = [
        DummyMenu(menu_id=1, title="系统管理", path="/system", parent_id=None, menu_type="0", sort_order=1),
        DummyMenu(menu_id=11, title="新增", path=None, parent_id=1, menu_type="2", sort_order=1),
        DummyMenu(menu_id=12, title="删除", path=None, parent_id=1, menu_type="2", sort_order=2),
    ]

    tree = build_menu_tree(menus)

    assert len(tree) == 1
    children = tree[0].get("children", [])
    assert len(children) == 2
    assert {item["label"] for item in children} == {"新增", "删除"}


def test_build_route_tree_filters_hash_path_and_keeps_children() -> None:
    menus = [
        DummyMenu(menu_id=1, title="系统管理", path="#", parent_id=None, menu_type="0", sort_order=1),
        DummyMenu(
            menu_id=2,
            title="租户设置",
            path="system/tenant/settings#features",
            parent_id=1,
            menu_type="1",
            sort_order=1,
        ),
    ]

    routes = build_route_tree(menus, user_menu_ids={1, 2}, is_superuser=True)

    assert len(routes) == 1
    assert routes[0]["path"] == "/__menu_group__/1"
    assert routes[0]["redirect"] == "/system/tenant/settings"
    assert routes[0]["children"][0]["path"] == "/system/tenant/settings"
