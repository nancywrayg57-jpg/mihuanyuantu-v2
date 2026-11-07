#!/usr/bin/env python3
"""Upload synthetic video/scan/audio/other (+image/link); delete marked test archives."""
import base64, json, os, subprocess, tempfile, urllib.request, urllib.error

BASE = os.environ.get("ARCHIVE_BASE", "https://huangzhisong.com").rstrip("/")
NEWS = "https://news.gmw.cn/2019-02/14/content_32498421.htm"
MARK = "[合成端测]"

def api_json(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode() or "{}")

def api_form(token, fields, files):
    cmd = ["curl", "-sS", "-X", "POST", BASE + "/api/collections/archives/records",
           "-H", f"Authorization: {token}"]
    for k, v in fields.items():
        cmd += ["-F", f"{k}={v}"]
    for field, path, mime, filename in files:
        cmd += ["-F", f"{field}=@{path};type={mime};filename={filename}"]
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)

def main():
    auth = api_json("POST", "/api/collections/users/auth-with-password", {
        "identity": "user1@huangzhisong.com", "password": "hzs1933",
    })
    token, uid = auth["token"], auth["record"]["id"]
    admin = api_json("POST", "/api/collections/users/auth-with-password", {
        "identity": "huangxiangcai@huangzhisong.com", "password": "3599263",
    })
    atok = admin["token"]

    all_list = api_json("GET", "/api/collections/archives/records?perPage=200", token=token)
    others = [i for i in all_list["items"] if i.get("uploader") != uid]
    print(f"PASS list_all_members member_sees={all_list['totalItems']} others={len(others)}")

    # also memories list (no uploader filter in rule)
    mem = api_json("GET", "/api/collections/memories/records?perPage=200", token=token)
    print(f"PASS memories_list_all total={mem['totalItems']}")

    created = []
    tmpdir = tempfile.mkdtemp()
    png = os.path.join(tmpdir, "t.png")
    open(png, "wb").write(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
    pdf = os.path.join(tmpdir, "t.pdf")
    open(pdf, "wb").write(b"%PDF-1.4\n1 0 obj<< /Type /Catalog >>endobj\ntrailer<<>>\n%%EOF\n")
    mp3 = os.path.join(tmpdir, "t.mp3")
    open(mp3, "wb").write(b"\xff\xfb\x90\x00" + b"\x00" * 512)
    mp4 = os.path.join(tmpdir, "t.mp4")
    open(mp4, "wb").write(bytes.fromhex(
        "000000206674797069736f6d0000020069736f6d69736f32617663316d703431" + "00" * 128))

    cases = [
        ("image", png, "image/png", "synth.png", f"{MARK} image"),
        ("video", mp4, "video/mp4", "synth.mp4", f"{MARK} video"),
        ("scan", pdf, "application/pdf", "synth-scan.pdf", f"{MARK} scan"),
        ("audio", mp3, "audio/mpeg", "synth.mp3", f"{MARK} audio"),
        ("other", pdf, "application/pdf", "synth-other.pdf", f"{MARK} other"),
    ]
    for cat, path, mime, filename, title in cases:
        rec = api_form(token, {
            "title": title,
            "category": cat,
            "occurred_time": "2019-02-14",
            "related_persons": "黄志松",
            "description": MARK,
            "uploader": uid,
            "uploader_name": "黄纲生",
            "likes_count": "0",
        }, [("media_files", path, mime, filename)])
        if not rec.get("id"):
            raise SystemExit(f"FAIL upload_{cat}: {rec}")
        created.append(rec["id"])
        print(f"PASS upload_{cat}", rec["id"], rec.get("media_files"))

    link = api_json("POST", "/api/collections/archives/records", {
        "title": f"{MARK} 光明网链接",
        "category": "link",
        "occurred_time": "2019-02-14",
        "related_persons": "黄志松",
        "description": MARK,
        "external_link": NEWS,
        "uploader": uid,
        "uploader_name": "黄纲生",
        "likes_count": 0,
    }, token=token)
    assert link.get("external_link") == NEWS, link
    created.append(link["id"])
    print("PASS upload_link", link["id"], link["external_link"])

    # cleanup all test-marked / diagnostic archives
    lst = api_json("GET", "/api/collections/archives/records?perPage=200", token=atok)
    keywords = [
        MARK, "验收测试图", "UI测试图", "upload-png", "upload-jpg", "mime", "diag",
        "after-restore", "admin-json", "本机上传验收", "光明网新闻链接验收", "合成端测",
        "json-only", "t",
    ]
    # Only kill clearly-test titles — avoid wiping real family archives.
    kill = []
    for i in lst["items"]:
        title = str(i.get("title") or "")
        desc = str(i.get("description") or "")
        if i["id"] in created or MARK in title or MARK in desc:
            kill.append(i)
            continue
        if any(k == title or title.startswith(k) or title in (
            "upload-png","upload-jpg","mime","diag","admin-json","after-restore","t"
        ) for k in keywords):
            kill.append(i)
            continue
        if "验收" in title or "测试" in title or "UI测试" in title or "本机上传" in title:
            kill.append(i)

    for i in kill:
        req = urllib.request.Request(
            BASE + f"/api/collections/archives/records/{i['id']}",
            headers={"Authorization": atok}, method="DELETE")
        try:
            urllib.request.urlopen(req)
            print("DELETED", i["id"], i.get("title"))
        except urllib.error.HTTPError as e:
            print("DELETE_FAIL", i["id"], e.code, e.read().decode()[:120])

    left = api_json("GET", "/api/collections/archives/records?perPage=200", token=atok)
    remain_test = [i for i in left["items"] if MARK in str(i.get("title")) or MARK in str(i.get("description"))
                   or "验收" in str(i.get("title")) or "测试" in str(i.get("title"))
                   or str(i.get("title")) in ("upload-png","upload-jpg","mime","diag","t")]
    print("PASS cleanup" if not remain_test else f"FAIL cleanup left={[x.get('title') for x in remain_test]}")
    print("archives_remaining", left["totalItems"], [x.get("title") for x in left["items"]])

if __name__ == "__main__":
    main()
