#!/usr/bin/env python3
"""Phase B item3: media preview fields, thumbs, cover/duration; cleanup."""
import json, os, re, subprocess, tempfile, urllib.request, urllib.error

BASE = os.environ.get("ARCHIVE_BASE", "https://huangzhisong.com").rstrip("/")
MARK = "[B3端测]"

def api(method, path, data=None, token=None, form_files=None):
    if form_files is not None:
        cmd = ["curl", "-sS", "-X", method, BASE + path]
        if token:
            cmd += ["-H", f"Authorization: {token}"]
        for k, v in (data or {}).items():
            if v is None or v == "":
                continue
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

    # schema
    at = json.load(urllib.request.urlopen(urllib.request.Request(
        BASE + "/api/admins/auth-with-password",
        data=json.dumps({"identity": "admin@huangzhisong.com", "password": "HbsAdmin#2026"}).encode(),
        headers={"Content-Type": "application/json"},
    )))["token"]
    col = json.load(urllib.request.urlopen(urllib.request.Request(
        BASE + "/api/collections/archives", headers={"Authorization": at})))
    names = {f["name"] for f in col["schema"]}
    assert "cover_file" in names and "duration_sec" in names, names
    print("PASS schema_cover_duration")

    tmp = tempfile.mkdtemp()
    png = os.path.join(tmp, "b3.png")
    # 64x64 red png via ffmpeg
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=64x64:d=1", "-frames:v", "1", png,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cover = os.path.join(tmp, "cover.jpg")
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x180:d=1", "-frames:v", "1", cover,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mp4 = os.path.join(tmp, "b3.mp4")
    subprocess.check_call([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=green:s=160x120:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "2", mp4,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    created = []
    img = api("POST", "/api/collections/archives/records", {
        "title": f"{MARK} image thumb",
        "category": "image",
        "occurred_time": "2019-02-14",
        "related_persons": "黄志松",
        "description": MARK,
        "uploader": uid,
        "uploader_name": "黄纲生",
        "likes_count": "0",
    }, token=token, form_files=[("media_files", png, "image/png", "b3.png")])
    assert img.get("id") and img.get("media_files"), img
    created.append(img["id"])
    fname = img["media_files"][0]
    thumb = f"{BASE}/api/files/{img['collectionId']}/{img['id']}/{fname}?thumb=600x0"
    req = urllib.request.Request(thumb, headers={"Authorization": token})
    with urllib.request.urlopen(req) as r:
        assert r.status == 200 and r.headers.get_content_type().startswith("image/"), r.headers
    print("PASS image_thumb_600x0")

    vid = api("POST", "/api/collections/archives/records", {
        "title": f"{MARK} video cover",
        "category": "video",
        "occurred_time": "2019-02-14",
        "related_persons": "黄志松",
        "description": MARK,
        "uploader": uid,
        "uploader_name": "黄纲生",
        "likes_count": "0",
        "duration_sec": "2",
        "playback_status": "native",
    }, token=token, form_files=[
        ("media_files", mp4, "video/mp4", "b3.mp4"),
        ("cover_file", cover, "image/jpeg", "cover.jpg"),
    ])
    assert vid.get("id"), vid
    created.append(vid["id"])
    assert vid.get("cover_file"), vid
    assert float(vid.get("duration_sec") or 0) >= 1, vid
    print("PASS video_cover_duration", vid.get("duration_sec"), vid.get("cover_file"))

    html = urllib.request.urlopen(BASE + "/").read().decode("utf-8", "ignore")
    js = "".join(
        urllib.request.urlopen(BASE + u).read().decode("utf-8", "ignore")
        for u in re.findall(r'src="(/assets/[^"]+\.js)"', html)
    )
    blob = html + js
    for m in ["upload-previews", "archive-thumb", "video-duration", "prep-notes", "compressImageFile"]:
        # compressImageFile may be minified — check Chinese/feature strings too
        ok = m in blob or ("已压缩" in blob and m == "compressImageFile") or ("已提取视频封面" in blob and m == "compressImageFile")
        if m == "compressImageFile":
            ok = ("已压缩" in blob) or ("compressImageFile" in blob) or ("IMAGE_MAX_EDGE" in blob) or ("上传前自动压缩" in blob)
        assert ok, f"missing marker {m}"
        print("PASS ui_marker", m)

    for i in created:
        urllib.request.urlopen(urllib.request.Request(
            BASE + f"/api/collections/archives/records/{i}",
            headers={"Authorization": atok}, method="DELETE"))
        print("DELETED", i)
    lst = api("GET", "/api/collections/archives/records?perPage=200", token=atok)
    for it in lst["items"]:
        if MARK in str(it.get("title")) or MARK in str(it.get("description")):
            urllib.request.urlopen(urllib.request.Request(
                BASE + f"/api/collections/archives/records/{it['id']}",
                headers={"Authorization": atok}, method="DELETE"))
    print("PASS b3_cleanup")

if __name__ == "__main__":
    main()
