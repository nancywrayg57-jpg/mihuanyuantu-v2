#!/usr/bin/env python3
"""Phase A item2: chunked resumable upload + size limit + cleanup."""
import json, os, subprocess, tempfile, urllib.request, urllib.error

BASE = os.environ.get("ARCHIVE_BASE", "https://huangzhisong.com").rstrip("/")
MARK = "[A2端测]"
CHUNK = 256 * 1024

def jreq(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode() or "{}")

def main():
    auth = jreq("POST", "/api/collections/users/auth-with-password", {
        "identity": "user1@huangzhisong.com", "password": "hzs1933",
    })
    token, uid = auth["token"], auth["record"]["id"]
    admin = jreq("POST", "/api/collections/users/auth-with-password", {
        "identity": "huangxiangcai@huangzhisong.com", "password": "3599263",
    })
    atok = admin["token"]

    # Build ~1.2MB binary so chunked path is used
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "a2.bin.pdf")
    # PDF header + padding (mime-friendly via .pdf name)
    data = b"%PDF-1.4\n" + (b"A2-CHUNK-TEST-" * 80000)
    open(path, "wb").write(data)
    size = os.path.getsize(path)
    assert size > 1024 * 1024, size

    # Reject oversize image cap via init
    try:
        jreq("POST", "/api/hz/upload/init", {
            "filename": "big.jpg", "size": 31 * 1024 * 1024, "mime": "image/jpeg",
            "category": "image", "title": "x", "occurred_time": "2019-02-14",
            "related_persons": "黄志松",
        }, token=token)
        raise SystemExit("FAIL expected size reject")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        assert e.code == 400 and "30" in body, body
        print("PASS size_limit_image_reject")

    init = jreq("POST", "/api/hz/upload/init", {
        "filename": "a2-chunk.pdf",
        "size": size,
        "mime": "application/pdf",
        "category": "other",
        "chunkSize": CHUNK,
        "title": f"{MARK} chunked other",
        "occurred_time": "2019-02-14",
        "related_persons": "黄志松",
        "description": MARK,
    }, token=token)
    sid = init["sessionId"]
    total = init["totalChunks"]
    print("PASS init", sid, "chunks", total, "size", size)

    # Upload all but last, check status (resume point)
    chunk_dir = os.path.join(tmp, "chunks")
    os.makedirs(chunk_dir, exist_ok=True)
    with open(path, "rb") as f:
        raw = f.read()
    for i in range(total - 1):
        part = raw[i * CHUNK:(i + 1) * CHUNK]
        cpath = os.path.join(chunk_dir, f"c{i}.bin")
        open(cpath, "wb").write(part)
        out = subprocess.check_output([
            "curl", "-sS", "-X", "POST", f"{BASE}/api/hz/upload/chunk/{sid}/{i}",
            "-H", f"Authorization: {token}",
            "-F", f"chunk=@{cpath};type=application/octet-stream;filename=chunk-{i}",
        ], text=True)
        assert json.loads(out).get("index") == i, out
    last = raw[(total - 1) * CHUNK:]
    last_path = os.path.join(chunk_dir, "clast.bin")
    open(last_path, "wb").write(last)

    st = jreq("GET", f"/api/hz/upload/status/{sid}", token=token)
    assert len(st["received"]) == total - 1, st
    print("PASS partial_status received", len(st["received"]))

    # resume last chunk + complete
    out = subprocess.check_output([
        "curl", "-sS", "-X", "POST", f"{BASE}/api/hz/upload/chunk/{sid}/{total-1}",
        "-H", f"Authorization: {token}",
        "-F", f"chunk=@{last_path};type=application/octet-stream;filename=chunk-last",
    ], text=True)
    assert json.loads(out).get("received") == total, out
    print("PASS resume_last_chunk")

    rec = jreq("POST", f"/api/hz/upload/complete/{sid}", {
        "title": f"{MARK} chunked other",
        "occurred_time": "2019-02-14",
        "related_persons": "黄志松",
        "description": MARK,
    }, token=token)
    assert rec.get("id") and rec.get("media_files"), rec
    print("PASS complete", rec["id"], rec.get("media_files"))

    # verify file downloadable and size matches roughly
    col = rec.get("collectionId") or "archives"
    fname = rec["media_files"][0] if isinstance(rec["media_files"], list) else rec["media_files"]
    req = urllib.request.Request(
        f"{BASE}/api/files/{col}/{rec['id']}/{fname}",
        headers={"Authorization": token})
    with urllib.request.urlopen(req) as r:
        blob = r.read()
    assert abs(len(blob) - size) <= 16, (len(blob), size)
    print("PASS assembled_size", len(blob))

    # frontend queue marker
    html = urllib.request.urlopen(BASE + "/").read().decode("utf-8", "ignore")
    import re
    js = "".join(urllib.request.urlopen(BASE + u).read().decode("utf-8", "ignore")
                 for u in re.findall(r'src="(/assets/[^"]+\.js)"', html))
    assert "upload-queue" in (html + js)
    print("PASS ui_marker upload-queue")

    # cleanup
    urllib.request.urlopen(urllib.request.Request(
        BASE + f"/api/collections/archives/records/{rec['id']}",
        headers={"Authorization": atok}, method="DELETE"))
    print("DELETED", rec["id"])
    lst = jreq("GET", "/api/collections/archives/records?perPage=200", token=atok)
    for it in lst["items"]:
        if MARK in str(it.get("title")) or MARK in str(it.get("description")):
            urllib.request.urlopen(urllib.request.Request(
                BASE + f"/api/collections/archives/records/{it['id']}",
                headers={"Authorization": atok}, method="DELETE"))
            print("DELETED leftover", it["id"])
    print("PASS a2_cleanup")

if __name__ == "__main__":
    main()
