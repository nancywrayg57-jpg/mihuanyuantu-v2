#!/usr/bin/env python3
"""Idempotent reset: all members -> hzs1933; admin 黄祥财 -> 3599263; minPasswordLength=6."""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ARCHIVE_BASE", "https://huangzhisong.com").rstrip("/")
ADMIN_EMAIL = os.environ.get("PB_ADMIN_EMAIL", "admin@huangzhisong.com")
ADMIN_PASSWORD = os.environ.get("PB_ADMIN_PASSWORD", "HbsAdmin#2026")
MEMBER_PASSWORD = "hzs1933"
SUPER_PASSWORD = "3599263"


def req(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    body = None if data is None else json.dumps(data).encode()
    request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "{}"
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw}
        raise RuntimeError(f"{method} {path} -> {e.code} {payload}") from e


def main():
    _, admin = req(
        "POST",
        "/api/admins/auth-with-password",
        {"identity": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    token = admin["token"]

    _, col = req("GET", "/api/collections/users", token=token)
    opts = dict(col.get("options") or {})
    opts.update(
        {
            "minPasswordLength": 6,
            "allowEmailAuth": True,
            "allowUsernameAuth": True,
            "allowOAuth2Auth": False,
            "requireEmail": True,
        }
    )
    req(
        "PATCH",
        f"/api/collections/{col['id']}",
        {
            "name": col["name"],
            "type": col["type"],
            "system": col["system"],
            "schema": col["schema"],
            "indexes": col.get("indexes") or [],
            "listRule": col.get("listRule"),
            "viewRule": col.get("viewRule"),
            "createRule": col.get("createRule"),
            "updateRule": col.get("updateRule"),
            "deleteRule": col.get("deleteRule"),
            "options": opts,
        },
        token=token,
    )
    print("minPasswordLength=6 ensured")

    _, users = req("GET", "/api/collections/users/records?perPage=200", token=token)
    reset = 0
    for u in users.get("items", []):
        if u.get("display_name") == "黄祥财" or u.get("role") == "admin":
            password = SUPER_PASSWORD
        else:
            password = MEMBER_PASSWORD
        req(
            "PATCH",
            f"/api/collections/users/records/{u['id']}",
            {"password": password, "passwordConfirm": password, "verified": True},
            token=token,
        )
        reset += 1
        print(f"reset {u.get('display_name')} ({u.get('email')})")

    # verify samples
    samples = [
        ("huangxiangcai@huangzhisong.com", SUPER_PASSWORD, "黄祥财"),
        ("user1@huangzhisong.com", MEMBER_PASSWORD, "黄纲生"),
        ("user24@huangzhisong.com", MEMBER_PASSWORD, "黄嘉颖"),
        ("user25@huangzhisong.com", MEMBER_PASSWORD, "张建华"),
    ]
    for email, pwd, name in samples:
        _, auth = req(
            "POST",
            "/api/collections/users/auth-with-password",
            {"identity": email, "password": pwd},
        )
        assert auth["record"]["display_name"] == name, auth
        print(f"verify OK {name}")

    print(f"done reset={reset} total={users.get('totalItems')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR", e, file=sys.stderr)
        sys.exit(1)
