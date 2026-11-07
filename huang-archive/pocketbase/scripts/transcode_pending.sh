#!/bin/sh
# Poll pending video archives and produce H.264/AAC MP4 for WeChat-friendly playback.
set -eu

PB_URL="${PB_URL:-http://127.0.0.1:8090}"
ADMIN_EMAIL="${PB_ADMIN_EMAIL:-admin@huangzhisong.com}"
ADMIN_PASS="${PB_ADMIN_PASSWORD:-HbsAdmin#2026}"
DATA_DIR="${PB_DATA_DIR:-/pb/pb_data}"
TMP_DIR="${DATA_DIR}/transcode_tmp"
mkdir -p "$TMP_DIR"

TOKEN="$(curl -fsS -X POST "$PB_URL/api/admins/auth-with-password" \
  -H 'Content-Type: application/json' \
  -d "{\"identity\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASS\"}" \
  | sed -n 's/.*"token":"\([^"]*\)".*/\1/p' || true)"
[ -n "$TOKEN" ] || exit 0

LIST="$(curl -fsS -G "$PB_URL/api/collections/archives/records" \
  --data-urlencode 'filter=category="video" && playback_status="pending"' \
  --data-urlencode 'perPage=5' \
  -H "Authorization: $TOKEN" || true)"
[ -n "$LIST" ] || exit 0

echo "$LIST" > "$TMP_DIR/pending.json"
python3 - "$TMP_DIR/pending.json" "$TMP_DIR/pending.tsv" <<'PY'
import json,sys
src,dst=sys.argv[1],sys.argv[2]
try:
  data=json.load(open(src))
except Exception:
  open(dst,"w").write(""); raise SystemExit(0)
lines=[]
for it in data.get("items") or []:
  files=it.get("media_files") or []
  first=files[0] if files else ""
  if not first: continue
  col=it.get("collectionId") or "archives"
  lines.append(f"{it['id']}\t{col}\t{first}")
open(dst,"w").write("\n".join(lines)+("\n" if lines else ""))
PY

[ -s "$TMP_DIR/pending.tsv" ] || exit 0

while IFS="$(printf '\t')" read -r ID COL FIRST; do
  [ -n "$ID" ] || continue
  IN="$TMP_DIR/${ID}_in"
  OUT="$TMP_DIR/${ID}_out.mp4"
  rm -f "$IN" "$OUT"

  if ! curl -fsS -o "$IN" -H "Authorization: $TOKEN" \
    "$PB_URL/api/files/$COL/$ID/$FIRST"; then
    curl -fsS -X PATCH "$PB_URL/api/collections/archives/records/$ID" \
      -H "Authorization: $TOKEN" -H 'Content-Type: application/json' \
      -d '{"playback_status":"failed","playback_note":"原视频下载失败，请下载原文件用系统播放器打开"}' >/dev/null || true
    continue
  fi

  if ffmpeg -y -i "$IN" -c:v libx264 -pix_fmt yuv420p -profile:v baseline -level 3.1 \
      -movflags +faststart -c:a aac -b:a 128k -ac 2 -ar 44100 \
      "$OUT" </dev/null >/tmp/hz_ffmpeg_${ID}.log 2>&1; then
    if ! curl -fsS -X PATCH "$PB_URL/api/collections/archives/records/$ID" \
      -H "Authorization: $TOKEN" \
      -F 'playback_status=ready' \
      -F 'playback_note=已转码为微信友好 MP4' \
      -F "playback_file=@${OUT};type=video/mp4;filename=playback.mp4" >/dev/null; then
      curl -fsS -X PATCH "$PB_URL/api/collections/archives/records/$ID" \
        -H "Authorization: $TOKEN" -H 'Content-Type: application/json' \
        -d '{"playback_status":"failed","playback_note":"转码成功但写回失败，请下载原文件"}' >/dev/null || true
    fi
  else
    curl -fsS -X PATCH "$PB_URL/api/collections/archives/records/$ID" \
      -H "Authorization: $TOKEN" -H 'Content-Type: application/json' \
      -d '{"playback_status":"failed","playback_note":"当前格式无法转码，请下载后用系统播放器打开"}' >/dev/null || true
  fi
  rm -f "$IN" "$OUT"
done < "$TMP_DIR/pending.tsv"
