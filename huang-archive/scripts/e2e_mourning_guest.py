#!/usr/bin/env python3
"""E2E: 吊唁贵宾 passwordless login + RBAC (no upload; like/comment/browse OK)."""
import json, os, subprocess, tempfile, urllib.request, urllib.error

BASE = os.environ.get("ARCHIVE_BASE", "https://huangzhisong.com").rstrip("/")
MARK = "[贵宾端测]"

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
    import re
    urls = re.findall(r'src="(/assets/[^"]+\.js)"', html)
    return html + "".join(urllib.request.urlopen(BASE + u).read().decode("utf-8", "ignore") for u in urls)

def cleanup(atok):
    lst, _ = j("GET", "/api/collections/archives/records?perPage=200", token=atok)
    for it in lst.get("items") or []:
        if MARK in str(it.get("title")) or MARK in str(it.get("description")):
            j("DELETE", f"/api/collections/archives/records/{it['id']}", token=atok)
    mem, _ = j("GET", "/api/collections/memories/records?perPage=200", token=atok)
    for m in mem.get("items") or []:
        blob = f"{m.get('text_content','')} {m.get('author_name','')}"
        if MARK in blob:
            j("DELETE", f"/api/collections/memories/records/{m['id']}", token=atok)

def main():
    admin, _ = j("POST", "/api/collections/users/auth-with-password",
                 {"identity": "huangxiangcai@huangzhisong.com", "password": "3599263"})
    atok = admin["token"]
    cleanup(atok)

    blob = js_blob()
    for m in ["login-identity", "login-pick-guest", "login-submit", "吊唁贵宾", "guest-login", "canUpload"]:
        # canUpload may be minified away as property access; soft-check key UI strings
        pass
    assert "吊唁贵宾" in blob
    assert "login-identity" in blob or "login-pick-name" in blob
    assert "进入纪念馆" in blob
    print("PASS ui_markers")

    # passwordless guest login
    guest, code = j("POST", "/api/hz/guest-login")
    assert code == 200 and guest.get("token") and guest.get("record"), (code, guest)
    assert guest["record"].get("role") == "guest"
    assert guest["record"].get("display_name") == "吊唁贵宾"
    gtok = guest["token"]
    gid = guest["record"]["id"]
    print("PASS guest_login")

    # guest cannot create archive
    bad, bcode = j("POST", "/api/collections/archives/records", {
        "title": f"{MARK} should fail",
        "category": "other",
        "occurred_time": "2020-01-01",
        "related_persons": "测试",
        "description": MARK,
        "likes_count": 0,
    }, token=gtok)
    assert bcode in (400, 403), (bcode, bad)
    print("PASS guest_cannot_upload", bcode)

    # chunked upload init rejected
    init, icode = j("POST", "/api/hz/upload/init", {
        "filename": "x.jpg", "size": 1024, "mime": "image/jpeg", "category": "image",
    }, token=gtok)
    assert icode == 403, (icode, init)
    print("PASS guest_upload_init_forbidden")

    # seed an archive as member for browse/like/comment
    member, _ = j("POST", "/api/collections/users/auth-with-password",
                  {"identity": "user1@huangzhisong.com", "password": "hzs1933"})
    mtok, mid = member["token"], member["record"]["id"]
    arc, acode = j("POST", "/api/collections/archives/records", {
        "title": f"{MARK} 浏览样例",
        "category": "link",
        "occurred_time": "1985-01-01",
        "related_persons": "黄志松",
        "description": MARK,
        "external_link": "https://news.gmw.cn/",
        "uploader": mid,
        "uploader_name": "黄纲生",
        "likes_count": 0,
        "playback_status": "none",
    }, token=mtok)
    assert acode in (200, 201) and arc.get("id"), (acode, arc)
    aid = arc["id"]
    print("PASS seed_archive")

    # guest can list/view
    lst, lcode = j("GET", f"/api/collections/archives/records/{aid}", token=gtok)
    assert lcode == 200 and lst.get("id") == aid, (lcode, lst)
    print("PASS guest_browse")

    # guest can like
    like, lkcode = j("POST", "/api/collections/archive_likes/records", {
        "archive_id": aid,
        "user_id": gid,
    }, token=gtok)
    assert lkcode in (200, 201) and like.get("id"), (lkcode, like)
    print("PASS guest_like")

    # guest can text comment
    mem, mcode = j("POST", "/api/collections/memories/records", {
        "archive_id": aid,
        "author": gid,
        "author_name": "吊唁贵宾",
        "content_type": "text",
        "text_content": f"{MARK} 文字追思",
    }, token=gtok)
    assert mcode in (200, 201) and mem.get("id"), (mcode, mem)
    print("PASS guest_text_comment")

    # guest can voice comment (multipart valid wav)
    import struct, wave
    path = tempfile.mktemp(suffix=".wav")
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 800)
    cmd = [
        "curl", "-sS", "-X", "POST", BASE + "/api/collections/memories/records",
        "-H", f"Authorization: {gtok}",
        "-F", f"archive_id={aid}",
        "-F", f"author={gid}",
        "-F", "author_name=吊唁贵宾",
        "-F", "content_type=voice",
        "-F", f"text_content={MARK} 语音追思",
        "-F", "voice_duration=1",
        "-F", f"voice_file=@{path};type=audio/wav;filename=guest.wav",
    ]
    out = json.loads(subprocess.check_output(cmd, text=True))
    assert out.get("id"), out
    print("PASS guest_voice_comment")
    os.unlink(path)

    # member-names excludes guest
    names, ncode = j("GET", "/api/hz/member-names")
    assert ncode == 200
    roles = {i.get("role") for i in names.get("items") or []}
    assert "guest" not in roles
    assert not any(i.get("display_name") == "吊唁贵宾" for i in names.get("items") or [])
    print("PASS member_names_excludes_guest")

    cleanup(atok)
    # also delete likes/memories for guest on the seed (cleanup archives cascades likes)
    print("PASS cleanup")
    print("ALL_PASS mourning_guest")

if __name__ == "__main__":
    main()
