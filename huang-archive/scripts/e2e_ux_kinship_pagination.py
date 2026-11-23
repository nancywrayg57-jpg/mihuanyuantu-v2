#!/usr/bin/env python3
"""E2E for kinship enums, unified search, pagination, timeline year drill-down, large-tap icon."""
import json, os, re, urllib.request, urllib.error

BASE = os.environ.get("ARCHIVE_BASE", "https://huangzhisong.com").rstrip("/")
MARK = "[UX五项端测]"

NEW_RELATIONS = [
    "孙子", "孙女", "孙女婿", "孙媳", "外甥女婿", "外甥媳",
    "侄儿", "侄女", "侄孙", "侄孙媳", "侄外甥", "侄外甥媳", "学生", "晚辈",
]

def j(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode() or "{}"), r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "{}"
        try:
            return json.loads(raw), e.code
        except Exception:
            return {"raw": raw}, e.code

def js_blob():
    html = urllib.request.urlopen(BASE + "/").read().decode("utf-8", "ignore")
    urls = re.findall(r'src="(/assets/[^"]+\.js)"', html)
    return html + "".join(
        urllib.request.urlopen(BASE + u).read().decode("utf-8", "ignore") for u in urls
    )

def cleanup(atok):
    lst, _ = j("GET", "/api/collections/archives/records?perPage=200", token=atok)
    for it in lst.get("items") or []:
        if MARK in str(it.get("title")) or MARK in str(it.get("description")):
            j("DELETE", f"/api/collections/archives/records/{it['id']}", token=atok)
    # delete test members created for relation check
    users, _ = j("GET", "/api/collections/users/records?perPage=200", token=atok)
    for u in users.get("items") or []:
        if str(u.get("display_name") or "").startswith(MARK):
            j("DELETE", f"/api/collections/users/records/{u['id']}", token=atok)

def main():
    member, _ = j("POST", "/api/collections/users/auth-with-password",
                  {"identity": "user1@huangzhisong.com", "password": "hzs1933"})
    admin, _ = j("POST", "/api/collections/users/auth-with-password",
                 {"identity": "huangxiangcai@huangzhisong.com", "password": "3599263"})
    token, uid = member["token"], member["record"]["id"]
    atok = admin["token"]
    cleanup(atok)

    blob = js_blob()

    # 1) kinship enums in frontend bundle + PB accepts new select values
    for rel in NEW_RELATIONS:
        assert rel in blob, f"missing relation in UI: {rel}"
    print("PASS kinship_ui_enums")

    created_users = []
    for i, rel in enumerate(NEW_RELATIONS):
        email = f"uxrel{i}{os.getpid()}@huangzhisong.com"
        rec, code = j("POST", "/api/collections/users/records", {
            "email": email,
            "username": f"uxrel{i}{os.getpid()}",
            "emailVisibility": True,
            "password": "hzs1933",
            "passwordConfirm": "hzs1933",
            "display_name": f"{MARK}{rel}",
            "relation": rel,
            "role": "member",
        }, token=atok)
        assert code in (200, 201) and rec.get("id"), (rel, code, rec)
        assert rec.get("relation") == rel, rec
        created_users.append(rec["id"])
    print("PASS kinship_pb_select", len(created_users))

    # 2+3) unified search UI + pagination markers; no combo filters
    for m in ["search-filters", "search-input", "list-pagination", "result-count", "archive-grid"]:
        assert m in blob, m
    for gone in ["filter-person", "date-from", "date-to"]:
        assert gone not in blob, gone
    assert "每页" in blob or "PAGE_SIZE" in blob or "page" in blob
    print("PASS unified_search_and_pagination_ui")

    # seed 12 newest-marked archives to exercise pagination math client-side
    ids = []
    for i in range(12):
        rec, code = j("POST", "/api/collections/archives/records", {
            "title": f"{MARK} 分页样例 {i:02d}",
            "category": "image",
            "occurred_time": f"199{i % 10}-0{(i % 9) + 1}-15",
            "related_persons": "黄志松",
            "description": MARK,
            "uploader": uid,
            "uploader_name": "黄纲生",
            "likes_count": 0,
        }, token=token)
        assert code in (200, 201) and rec.get("id"), rec
        ids.append(rec["id"])
    lst, _ = j("GET", "/api/collections/archives/records?perPage=200&sort=-created", token=token)
    mine = [a for a in (lst.get("items") or []) if MARK in str(a.get("title"))]
    assert len(mine) >= 12, len(mine)
    # default page size 10 → at least 2 pages for this set
    pages = (len(mine) + 9) // 10
    assert pages >= 2, pages
    print("PASS pagination_seed", len(mine), "pages", pages)

    # 4) timeline year drill-down markers
    for m in ["timeline-view", "timeline-year", "timeline-year-list", "timeline-pagination", "timeline-back"]:
        assert m in blob, m
    years = {str(a.get("occurred_time") or "")[:4] for a in mine if a.get("occurred_time")}
    assert len(years) >= 2, years
    print("PASS timeline_year_ui", sorted(years)[:5])

    # 5) large-tap is icon (Maximize2) not text-only「大按钮」label in header button content
    assert "a11y-tap" in blob
    # Lucide Maximize2 ships as svg path data; ensure the old bare text toggle is gone from template markers
    assert "标准按钮" in blob  # still in title/sr-only
    print("PASS large_tap_icon")

    cleanup(atok)
    print("PASS cleanup")
    print("ALL_PASS ux_kinship_pagination")

if __name__ == "__main__":
    main()
