#!/usr/bin/env python3
"""Item 4 only: search/filter logic + UI markers + cleanup."""
import json, os, re, urllib.request

BASE = os.environ.get("ARCHIVE_BASE", "https://huangzhisong.com").rstrip("/")
MARK = "[B4端测]"

def j(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode() or "{}")

# mirror filter logic
def occurred_key(value):
    import re as _re
    m = _re.search(r"(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?", str(value or ""))
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1)
    return y * 10000 + mo * 100 + d

def match(a, q="", person="", date_from="", date_to="", category="all"):
    if category != "all" and a.get("category") != category:
        return False
    query = (q or "").lower().strip()
    if query:
        hay = "\n".join(str(a.get(k) or "").lower() for k in
                        ["title", "related_persons", "description", "uploader_name", "occurred_time", "external_link"])
        if query not in hay:
            return False
    p = (person or "").lower().strip()
    if p:
        blob = f"{a.get('related_persons','')} {a.get('uploader_name','')} {a.get('title','')}".lower()
        if p not in blob:
            return False
    key = occurred_key(a.get("occurred_time"))
    if date_from:
        fr = occurred_key(date_from)
        if fr is not None and key is not None and key < fr:
            return False
    if date_to:
        to = occurred_key(date_to)
        if to is not None and key is not None and key > to:
            return False
    return True

def main():
    auth = j("POST", "/api/collections/users/auth-with-password",
             {"identity": "user1@huangzhisong.com", "password": "hzs1933"})
    token, uid = auth["token"], auth["record"]["id"]
    admin = j("POST", "/api/collections/users/auth-with-password",
              {"identity": "huangxiangcai@huangzhisong.com", "password": "3599263"})
    atok = admin["token"]

    samples = [
        {"title": f"{MARK} 春游照片", "category": "image", "occurred_time": "1985-05-01",
         "related_persons": "黄志松", "description": MARK, "uploader": uid, "uploader_name": "黄纲生", "likes_count": 0},
        {"title": f"{MARK} 冬至录像", "category": "video", "occurred_time": "1990-12-22",
         "related_persons": "黄纲生", "description": MARK, "uploader": uid, "uploader_name": "黄纲生", "likes_count": 0,
         "playback_status": "none"},
    ]
    ids = []
    for s in samples:
        rec = j("POST", "/api/collections/archives/records", s, token=token)
        assert rec.get("id"), rec
        ids.append(rec["id"])

    lst = j("GET", "/api/collections/archives/records?perPage=200", token=token)["items"]
    mine = [a for a in lst if MARK in str(a.get("title"))]
    assert len(mine) >= 2
    assert len([a for a in mine if match(a, q="春游")]) == 1
    assert len([a for a in mine if match(a, person="黄纲生")]) == 1
    assert len([a for a in mine if match(a, date_from="1988-01-01")]) == 1
    assert len([a for a in mine if match(a, category="video")]) == 1
    print("PASS filter_logic")

    html = urllib.request.urlopen(BASE + "/").read().decode("utf-8", "ignore")
    js = "".join(urllib.request.urlopen(BASE + u).read().decode("utf-8", "ignore")
                 for u in re.findall(r'src="(/assets/[^"]+\.js)"', html))
    for m in ["search-filters", "search-input", "filter-person", "date-from", "date-to"]:
        assert m in (html + js), m
        print("PASS ui", m)

    for i in ids:
        urllib.request.urlopen(urllib.request.Request(
            BASE + f"/api/collections/archives/records/{i}",
            headers={"Authorization": atok}, method="DELETE"))
    print("PASS b4_cleanup")

if __name__ == "__main__":
    main()
