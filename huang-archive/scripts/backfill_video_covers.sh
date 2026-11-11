#!/bin/sh
# Backfill cover_file for video archives missing a cover (ffmpeg frame extract).
# Intended to run inside huang-pb or on host with PB admin + ffmpeg.
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
[ -n "$TOKEN" ] || { echo "admin auth failed" >&2; exit 1; }

LIST="$(curl -fsS -G "$PB_URL/api/collections/archives/records" \
  --data-urlencode 'filter=category="video" && (cover_file="" || cover_file=null)' \
  --data-urlencode 'perPage=50' \
  -H "Authorization: $TOKEN" || true)"
[ -n "$LIST" ] || exit 0

echo "$LIST" > "$TMP_DIR/nocover.json"
python3 - "$TMP_DIR/nocover.json" "$TMP_DIR/nocover.tsv" <<'PY'
import json,sys,re
src,dst=sys.argv[1],sys.argv[2]
try:
  data=json.load(open(src))
except Exception:
  open(dst,"w").write(""); raise SystemExit(0)
lines=[]
for it in data.get("items") or []:
  files=it.get("media_files") or []
  play=it.get("playback_file") or ""
  if isinstance(play, list): play = play[0] if play else ""
  first=files[0] if files else ""
  # Prefer playable mp4 for frame grab
  src_name = play if re.search(r"\.mp4$", str(play), re.I) else first
  if not src_name: continue
  if not re.search(r"\.(mp4|m4v|webm|mov|avi|mkv)$", str(src_name), re.I):
    # media may be a mistaken jpg; skip if no video
    if not play: continue
    src_name = play
  col=it.get("collectionId") or "archives"
  lines.append(f"{it['id']}\t{col}\t{src_name}")
open(dst,"w").write("\n".join(lines)+("\n" if lines else ""))
print(f"backfill candidates: {len(lines)}")
PY

[ -s "$TMP_DIR/nocover.tsv" ] || { echo "no videos missing cover"; exit 0; }

while IFS="$(printf '\t')" read -r ID COL SRC; do
  [ -n "$ID" ] || continue
  IN="$TMP_DIR/cover_${ID}_in"
  OUT="$TMP_DIR/cover_${ID}.jpg"
  rm -f "$IN" "$OUT"
  echo "extract cover for $ID from $SRC"
  if ! curl -fsS -o "$IN" -H "Authorization: $TOKEN" \
    "$PB_URL/api/files/$COL/$ID/$SRC"; then
    echo "download failed $ID" >&2
    continue
  fi
  if ffmpeg -y -ss 0.3 -i "$IN" -frames:v 1 -q:v 3 "$OUT" </dev/null \
      >/tmp/hz_cover_${ID}.log 2>&1 \
    || ffmpeg -y -i "$IN" -frames:v 1 -q:v 3 "$OUT" </dev/null \
      >/tmp/hz_cover_${ID}.log 2>&1; then
    :
  else
    echo "ffmpeg failed $ID — will try image media fallback" >&2
    rm -f "$OUT"
  fi
  if [ ! -s "$OUT" ]; then
    # Fallback: first media image already on the record
    META="$(curl -fsS -H "Authorization: $TOKEN" "$PB_URL/api/collections/archives/records/$ID" || true)"
    IMG="$(printf '%s' "$META" | python3 -c 'import json,sys,re; d=json.load(sys.stdin); 
fs=d.get("media_files") or [];
print(next((f for f in fs if re.search(r"\.(jpe?g|png|webp)$", f, re.I)), ""), end="")' 2>/dev/null || true)"
    if [ -n "$IMG" ]; then
      curl -fsS -o "$OUT" -H "Authorization: $TOKEN" "$PB_URL/api/files/$COL/$ID/$IMG" || true
    fi
  fi
  if [ -s "$OUT" ]; then
    curl -fsS -X PATCH "$PB_URL/api/collections/archives/records/$ID" \
      -H "Authorization: $TOKEN" \
      -F "cover_file=@${OUT};type=image/jpeg;filename=cover.jpg" >/dev/null \
      && echo "OK $ID" || echo "PATCH failed $ID" >&2
  else
    echo "no cover produced $ID" >&2
  fi
  rm -f "$IN" "$OUT"
done < "$TMP_DIR/nocover.tsv"

echo "backfill_video_covers done"
