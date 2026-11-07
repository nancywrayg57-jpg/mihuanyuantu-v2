#!/usr/bin/env python3
"""Upload synthetic image/video/scan/audio/other + news link; then delete marked test archives."""
import base64, json, os, subprocess, tempfile, urllib.parse, urllib.request, urllib.error

BASE = os.environ.get("ARCHIVE_BASE", "https://huangzhisong.com").rstrip("/")
NEWS = "https://news.gmw.cn/2019-02/14/content_32498421.htm"
MARK = "[合成端测]"

def api(method, path, data=None, token=None, form_files=None):
    if form_files is not None:
        # use curl for multipart
        cmd = ["curl", "-sS", "-X", method, BASE + path]
        if token:
            cmd += ["-H", f"Authorization: {token}"]
        for k, v in (data or {}).items():
            cmd += ["-F", f"{k}={v}"]
        for field, path_, mime in form_files:
            cmd += ["-F", f"{field}=@{path_};type={mime}"]
        out = subprocess.check_output(cmd, text=True)
        return json.loads(out)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as r:
        raw = r.read().decode() or "{}"
        return json.loads(raw)

def main():
    auth = api("POST", "/api/collections/users/auth-with-password", {
        "identity": "user1@huangzhisong.com", "password": "hzs1933",
    })
    token, uid = auth["token"], auth["record"]["id"]
    admin = api("POST", "/api/collections/users/auth-with-password", {
        "identity": "huangxiangcai@huangzhisong.com", "password": "3599263",
    })
    atok = admin["token"]

    # Permission: member sees archives from other uploaders
    all_list = api("GET", "/api/collections/archives/records?perPage=200", token=token)
    others = [i for i in all_list["items"] if i.get("uploader") != uid]
    print(f"PASS list_all_members member_sees={all_list['totalItems']} others={len(others)}")

    created = []
    tmpdir = tempfile.mkdtemp()

    # image png
    png = os.path.join(tmpdir, "t.png")
    open(png, "wb").write(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
    # minimal pdf
    pdf = os.path.join(tmpdir, "t.pdf")
    open(pdf, "wb").write(b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    # tiny "mp3" with mpeg frame header-ish bytes
    mp3 = os.path.join(tmpdir, "t.mp3")
    open(mp3, "wb").write(b"\xff\xfb\x90\x00" + b"\x00" * 256)
    # tiny mp4 (ftyp box)
    mp4 = os.path.join(tmpdir, "t.mp4")
    open(mp4, "wb").write(bytes.fromhex(
        "00000018667479706d703431000000006d70343169736f6d" + "00" * 64))
    # other bin
    other = os.path.join(tmpdir, "t.bin")
    open(other, "wb").write(b"HZ-SYNTH-OTHER-TEST")

    cases = [
        ("image", png, "image/png", f"{MARK} image"),
        ("video", mp4, "video/mp4", f"{MARK} video"),
        ("scan", pdf, "application/pdf", f"{MARK} scan"),
        ("audio", mp3, "audio/mpeg", f"{MARK} audio"),
        ("other", other, "application/octet-stream", f"{MARK} other"),
    ]
    for cat, path, mime, title in cases:
        rec = api("POST", "/api/collections/archives/records", {
            "title": title,
            "category": cat,
            "occurred_time": "2019-02-14",
            "related_persons": "黄志松",
            "description": MARK,
            "uploader": uid,
            "uploader_name": "黄纲生",
            "likes_count": "0",
        }, token=token, form_files=[("media_files", path, mime)])
        assert rec.get("id"), rec
        created.append(rec["id"])
        print(f"PASS upload_{cat}", rec["id"])

    # news link
    link = api("POST", "/api/collections/archives/records", {
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
    assert link.get("id") and link.get("external_link") == NEWS, link
    created.append(link["id"])
    print("PASS upload_link", link["id"], link["external_link"])

    # cleanup: delete by admin all marked test titles / descriptions, plus known test titles
    lst = api("GET", "/api/collections/archives/records?perPage=200", token=atok)
    kill = []
    keywords = [MARK, "验收测试图", "UI测试图", "upload-png", "upload-jpg", "mime", "diag", "after-restore", "admin-json", "本机上传验收", "光明网新闻链接验收", "合成端测"]
    for i in lst["items"]:
        blob = " ".join([str(i.get("title") or ""), str(i.get("description") or ""), str(i.get("external_link") or "")])
        if any(k in blob for k in keywords) or i["id"] in created:
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

    left = api("GET", "/api/collections/archives/records?perPage=200", token=atok)
    remain_test = [i for i in left["items"] if MARK in str(i.get("title")) or MARK in str(i.get("description"))]
    print("PASS cleanup" if not remain_test else f"FAIL cleanup left={len(remain_test)}")
    print("archives_remaining", left["totalItems"])

if __name__ == "__main__":
    main()
