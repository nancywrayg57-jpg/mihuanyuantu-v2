from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from app.api.deps import PermissionChecker
from app.capabilities.sample_items.api import router
from app.capabilities.sample_items.permissions import (
    ALL_PERMISSIONS,
    CREATE,
    DELETE,
    READ,
    UPDATE,
)

EXPECTED = {
    ("GET", ""): READ,
    ("GET", "/{item_id}"): READ,
    ("POST", ""): CREATE,
    ("PATCH", "/{item_id}"): UPDATE,
    ("DELETE", "/{item_id}"): DELETE,
}


def permission_checkers() -> dict[tuple[str, str], PermissionChecker]:
    checkers: dict[tuple[str, str], PermissionChecker] = {}
    for route in router.routes:
        assert isinstance(route, APIRoute)
        dependencies = [
            dependency.call
            for dependency in route.dependant.dependencies
            if isinstance(dependency.call, PermissionChecker)
        ]
        assert len(dependencies) == 1
        method = next(iter(route.methods - {"HEAD", "OPTIONS"}))
        checkers[(method, route.path)] = dependencies[0]
    return checkers


def assert_permission_contract() -> None:
    checkers = permission_checkers()
    assert set(checkers) == set(EXPECTED)
    for endpoint, expected_permission in EXPECTED.items():
        assert checkers[endpoint].required_permissions == {expected_permission}
    assert set(ALL_PERMISSIONS) == {READ, CREATE, UPDATE, DELETE}
    assert {permission for checker in checkers.values() for permission in checker.required_permissions} == set(
        ALL_PERMISSIONS
    )


def test_endpoint_permission_mapping_is_bidirectional_and_mutation_sensitive() -> None:
    assert_permission_contract()
    create_checker = permission_checkers()[("POST", "")]
    original = set(create_checker.required_permissions)
    create_checker.required_permissions.add(READ)
    try:
        with pytest.raises(AssertionError):
            assert_permission_contract()
    finally:
        create_checker.required_permissions = original
    assert_permission_contract()
