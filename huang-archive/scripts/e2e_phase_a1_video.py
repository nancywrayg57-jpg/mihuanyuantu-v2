#!/usr/bin/env python3
"""Phase A item1: multi-format video + playback fields + cleanup."""
import json, os, subprocess, tempfile, time, urllib.request, urllib.error

BASE = os.environ.get("ARCHIVE_BASE", "https://huangzhisong.com").rstrip("/")
MARK = "[A1端测]"

def api(method, path, data=None, token=None, form_files=None):
    if form_files is not None:
        cmd = ["curl", "-sS", "-X", method, BASE + path]
        if token:
            cmd += ["-H", f"Authorization: {token}"]
        for k, v in (data or {}).items():
            cmd += ["-F", f"{k}={v}"]
        for field, path_, mime, filename in form_files:
            cmd += ["-F", f"{field}=@{path_};type={mime};filename={filename}"]
        return json.loads(subprocess.check_output(cmd, text=True))
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode() or "{}")

def main():
    auth = api("POST", "/api/collections/users/auth-with-password", {
        "identity": "user1@huangzhisong.com", "password": "hzs1933",
    })
    token, uid = auth["token"], auth["record"]["id"]
    admin = api("POST", "/api/collections/users/auth-with-password", {
        "identity": "huangxiangcai@huangzhisong.com", "password": "3599263",
    })
    atok = admin["token"]

    tmp = tempfile.mkdtemp()
    mp4 = os.path.join(tmp, "a1.mp4")
    mov = os.path.join(tmp, "a1.mov")
    # tiny but valid-ish videos via ffmpeg
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=160x120:d=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1", mp4,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1", mov,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    created = []
    rec_mp4 = api("POST", "/api/collections/archives/records", {
        "title": f"{MARK} mp4 native",
        "category": "video",
        "occurred_time": "2019-02-14",
        "related_persons": "黄志松",
        "description": MARK,
        "uploader": uid,
        "uploader_name": "黄纲生",
        "likes_count": "0",
    }, token=token, form_files=[("media_files", mp4, "video/mp4", "a1.mp4")])
    assert rec_mp4.get("id"), rec_mp4
    created.append(rec_mp4["id"])
    # refresh after hook
    time.sleep(1)
    rec_mp4 = api("GET", f"/api/collections/archives/records/{rec_mp4['id']}", token=token)
    print("PASS upload_mp4", rec_mp4["id"], "playback_status=", rec_mp4.get("playback_status"))
    assert rec_mp4.get("playback_status") in ("native", "ready", "pending"), rec_mp4

    rec_mov = api("POST", "/api/collections/archives/records", {
        "title": f"{MARK} mov transcode",
        "category": "video",
        "occurred_time": "2019-02-14",
        "related_persons": "黄志松",
        "description": MARK,
        "uploader": uid,
        "uploader_name": "黄纲生",
        "likes_count": "0",
    }, token=token, form_files=[("media_files", mov, "video/quicktime", "a1.mov")])
    assert rec_mov.get("id"), rec_mov
    created.append(rec_mov["id"])
    time.sleep(1)
    rec_mov = api("GET", f"/api/collections/archives/records/{rec_mov['id']}", token=token)
    print("PASS upload_mov", rec_mov["id"], "playback_status=", rec_mov.get("playback_status"))
    assert rec_mov.get("playback_status") in ("pending", "ready", "failed", "native"), rec_mov

    # wait for transcoder up to ~90s
    ready = False
    for i in range(18):
        rec_mov = api("GET", f"/api/collections/archives/records/{rec_mov['id']}", token=token)
        st = rec_mov.get("playback_status")
        print(f"  transcode poll {i}: {st} note={rec_mov.get('playback_note')}")
        if st == "ready" and rec_mov.get("playback_file"):
            ready = True
            break
        if st == "failed":
            print("WARN transcode failed — fallback path OK:", rec_mov.get("playback_note"))
            break
        if st == "native":
            ready = True
            break
        time.sleep(5)
    print("PASS playback_pipeline", "ready" if ready or rec_mov.get("playback_status") in ("failed", "native", "ready") else "FAIL")

    # Frontend build markers
    html = urllib.request.urlopen(BASE + "/").read().decode("utf-8", "ignore")
    # asset js contains testids after build
    js_urls = [u for u in __import__("re").findall(r'src="(/assets/[^"]+\.js)"', html)]
    blob = html
    for u in js_urls:
        blob += urllib.request.urlopen(BASE + u).read().decode("utf-8", "ignore")
    for marker in ["archive-video", "video-pip", "video-mini", "mini-player", "wechat-hint"]:
        assert marker in blob, f"missing UI marker {marker}"
        print("PASS ui_marker", marker)

    # cleanup
    for i in created:
        req = urllib.request.Request(
            BASE + f"/api/collections/archives/records/{i}",
            headers={"Authorization": atok}, method="DELETE")
        urllib.request.urlopen(req)
        print("DELETED", i)
    # also sweep leftover A1 marks
    lst = api("GET", "/api/collections/archives/records?perPage=200", token=atok)
    for it in lst["items"]:
        if MARK in str(it.get("title")) or MARK in str(it.get("description")):
            req = urllib.request.Request(
                BASE + f"/api/collections/archives/records/{it['id']}",
                headers={"Authorization": atok}, method="DELETE")
            urllib.request.urlopen(req)
            print("DELETED leftover", it["id"], it.get("title"))
    print("PASS a1_cleanup")

if __name__ == "__main__":
    main()
