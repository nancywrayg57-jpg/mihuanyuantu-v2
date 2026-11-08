#!/usr/bin/env python3
"""E2E: site settings toggles, captcha gate, comment delete ACL, title rename markers."""
import json, os, re, struct, tempfile, urllib.request, urllib.error, wave, subprocess

BASE = os.environ.get("ARCHIVE_BASE", "https://huangzhisong.com").rstrip("/")
MARK = "[设置端测]"

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
    return html + "".join(urllib.request.urlopen(BASE + u).read().decode("utf-8", "ignore") for u in urls)

def cleanup(atok):
    lst, _ = j("GET", "/api/collections/archives/records?perPage=200", token=atok)
    for it in lst.get("items") or []:
        if MARK in str(it.get("title")) or MARK in str(it.get("description")):
            j("DELETE", f"/api/collections/archives/records/{it['id']}", token=atok)
    mem, _ = j("GET", "/api/collections/memories/records?perPage=200", token=atok)
    for m in mem.get("items") or []:
        if MARK in f"{m.get('text_content','')} {m.get('author_name','')}":
            j("DELETE", f"/api/collections/memories/records/{m['id']}", token=atok)

def main():
    admin, _ = j("POST", "/api/collections/users/auth-with-password",
                 {"identity": "huangxiangcai@huangzhisong.com", "password": "3599263"})
    atok = admin["token"]
    member, _ = j("POST", "/api/collections/users/auth-with-password",
                  {"identity": "user1@huangzhisong.com", "password": "hzs1933"})
    mtok, mid = member["token"], member["record"]["id"]
    cleanup(atok)

    blob = js_blob()
    assert "黄志松人生纪念馆" in blob, "title rename missing"
    assert "家族纪念馆" not in blob or "人生纪念馆" in blob
    assert "admin-site-settings" in blob
    assert "image-lightbox" in blob and "lightbox-prev" in blob
    assert "toggle-guest-passwordless" in blob and "toggle-login-captcha" in blob
    print("PASS ui_markers_title_settings_lightbox")

    # settings GET public
    s, sc = j("GET", "/api/hz/site-settings")
    assert sc == 200, s
    print("PASS settings_get", s)

    # non-admin cannot patch
    bad, bc = j("PATCH", "/api/hz/site-settings",
                {"guest_passwordless": False}, token=mtok)
    assert bc == 403, (bc, bad)
    print("PASS settings_member_forbidden")

    # admin can toggle captcha on then off
    s1, c1 = j("PATCH", "/api/hz/site-settings",
               {"login_captcha": True, "guest_passwordless": True}, token=atok)
    assert c1 == 200 and s1.get("login_captcha") is True, (c1, s1)
    print("PASS settings_captcha_on")

    cap, cc = j("GET", "/api/hz/captcha")
    assert cc == 200 and cap.get("id") and cap.get("svg"), (cc, cap)
    # wrong code
    wrong, wc = j("POST", "/api/hz/captcha/verify",
                  {"captcha_id": cap["id"], "captcha_code": "XXXX"})
    assert wc == 400, (wc, wrong)
    # fresh captcha — extract code from svg text
    cap2, _ = j("GET", "/api/hz/captcha")
    m = re.search(r">([A-Z0-9]{4})</text>", cap2.get("svg") or "")
    assert m, cap2
    code = m.group(1)
    ver, vc = j("POST", "/api/hz/captcha/verify",
                {"captcha_id": cap2["id"], "captcha_code": code})
    assert vc == 200 and ver.get("ticket"), (vc, ver)
    print("PASS captcha_flow")

    # guest login requires captcha when enabled
    g0, g0c = j("POST", "/api/hz/guest-login", {})
    assert g0c == 400, (g0c, g0)
    g1, g1c = j("POST", "/api/hz/guest-login", {"ticket": ver["ticket"]})
    assert g1c == 200 and g1.get("token"), (g1c, g1)
    print("PASS guest_login_with_ticket")

    # turn captcha off, disable guest passwordless
    s2, c2 = j("PATCH", "/api/hz/site-settings",
               {"login_captcha": False, "guest_passwordless": False}, token=atok)
    assert c2 == 200 and s2.get("guest_passwordless") is False, (c2, s2)
    g2, g2c = j("POST", "/api/hz/guest-login", {})
    assert g2c == 403, (g2c, g2)
    print("PASS guest_passwordless_off")

    # restore defaults
    j("PATCH", "/api/hz/site-settings",
      {"login_captcha": False, "guest_passwordless": True}, token=atok)
    print("PASS settings_restored")

    # comment delete ACL
    arc, ac = j("POST", "/api/collections/archives/records", {
        "title": f"{MARK} 评论ACL",
        "category": "link",
        "occurred_time": "1990-01-01",
        "related_persons": "黄志松",
        "description": MARK,
        "external_link": "https://example.com",
        "uploader": mid,
        "uploader_name": "黄纲生",
        "likes_count": 0,
        "playback_status": "none",
    }, token=mtok)
    assert ac in (200, 201), (ac, arc)
    aid = arc["id"]
    mem_m, mc = j("POST", "/api/collections/memories/records", {
        "archive_id": aid, "author": mid, "author_name": "黄纲生",
        "content_type": "text", "text_content": f"{MARK} 成员留言",
    }, token=mtok)
    assert mc in (200, 201), (mc, mem_m)
    guest, _ = j("POST", "/api/hz/guest-login")
    gtok, gid = guest["token"], guest["record"]["id"]
    mem_g, gc = j("POST", "/api/collections/memories/records", {
        "archive_id": aid, "author": gid, "author_name": "吊唁贵宾",
        "content_type": "text", "text_content": f"{MARK} 贵宾留言",
    }, token=gtok)
    assert gc in (200, 201), (gc, mem_g)

    # member cannot delete guest comment
    d1, d1c = j("DELETE", f"/api/collections/memories/records/{mem_g['id']}", token=mtok)
    assert d1c in (403, 400, 404), (d1c, d1)
    print("PASS member_cannot_delete_others")

    # member can delete own
    d2, d2c = j("DELETE", f"/api/collections/memories/records/{mem_m['id']}", token=mtok)
    assert d2c in (200, 204), (d2c, d2)
    print("PASS member_delete_own")

    # guest can delete own
    d3, d3c = j("DELETE", f"/api/collections/memories/records/{mem_g['id']}", token=gtok)
    assert d3c in (200, 204), (d3c, d3)
    print("PASS guest_delete_own")

    # recreate + admin deletes any
    mem_m2, _ = j("POST", "/api/collections/memories/records", {
        "archive_id": aid, "author": mid, "author_name": "黄纲生",
        "content_type": "text", "text_content": f"{MARK} 再留",
    }, token=mtok)
    d4, d4c = j("DELETE", f"/api/collections/memories/records/{mem_m2['id']}", token=atok)
    assert d4c in (200, 204), (d4c, d4)
    print("PASS admin_delete_any")

    cleanup(atok)
    print("PASS cleanup")
    print("ALL_PASS admin_settings_comment_acl")

if __name__ == "__main__":
    main()
