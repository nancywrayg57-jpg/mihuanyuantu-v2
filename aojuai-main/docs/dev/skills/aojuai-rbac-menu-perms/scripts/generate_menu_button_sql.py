#!/usr/bin/env python3
"""
AOJUAI Skill Script: generate_menu_button_sql.py

Generate a JSON payload (and optional curl) for creating a button menu (menu_type="2")
via the superuser MenuCreate endpoint.
"""

from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MenuCreate payload for a button permission menu.")
    parser.add_argument("--title", required=True, help="menu title, e.g. 项目新增")
    parser.add_argument("--perms", required=True, help="permission code, e.g. project:create")
    parser.add_argument("--parent-id", type=int, default=None, help="parent menu id (page menu id)")
    parser.add_argument("--sort-order", type=int, default=0, help="sortOrder")
    parser.add_argument("--tenant-id", type=int, default=None, help="optional tenantId field if you use custom APIs")
    parser.add_argument("--print-curl", action="store_true", help="print a curl example for /api/v1/menus/create")
    args = parser.parse_args()

    payload: dict[str, object] = {
        "title": args.title,
        "parentId": args.parent_id,
        "menuType": "2",
        "perms": args.perms,
        "sortOrder": args.sort_order,
        "isVisible": False,
        "isCache": False,
        "isFrame": False,
        "isActive": True,
        "alwaysShow": False,
        "meta": {},
    }
    # remove nulls for cleaner copy/paste
    payload = {k: v for k, v in payload.items() if v is not None}

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.print_curl:
        print("")
        print("# Example (needs superuser login token):")
        print("curl -X POST 'http://127.0.0.1:38000/api/v1/menus/create' \\")
        print("  -H 'Content-Type: application/json' \\")
        print("  -H 'Authorization: Bearer <ACCESS_TOKEN>' \\")
        print(f"  -d '{json.dumps(payload, ensure_ascii=False)}'")


if __name__ == "__main__":
    main()

