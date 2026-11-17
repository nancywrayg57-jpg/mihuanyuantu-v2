#!/bin/sh
# T3-e: install the exif-demo vhost from the repo template (source of truth).
#
# 2026-11-17：配置真源移入仓库，避免「shared 模板 25m / 现网 200m」的双份漂移。
# - 模板：同目录 nginx.exif-demo.app.conf.template（含 client_max_body_size 200m）
# - 密钥：x-aoju-proxy-key 由 shared/backend.env 的 AOJ_PROXY_SHARED_SECRET 注入
# - 回滚：首次运行会备份占位配置到 shared/nginx-exif-demo.placeholder.conf
set -eu
export LANG=C.UTF-8

SH=/root/蜜獾原图-v2/shared
SITE=/etc/nginx/sites-enabled/exif-demo.honeybadgersoft.com.conf
AVAIL=/etc/nginx/sites-available/exif-demo.honeybadgersoft.com.conf
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TEMPLATE="${NGINX_TEMPLATE:-$SCRIPT_DIR/nginx.exif-demo.app.conf.template}"

if [ ! -f "$TEMPLATE" ]; then
  echo "template not found: $TEMPLATE" >&2
  exit 1
fi

# 1) 备份占位配置（只做一次）
if [ ! -f "$SH/nginx-exif-demo.placeholder.conf" ]; then
  cp -L "$SITE" "$SH/nginx-exif-demo.placeholder.conf"
  echo "placeholder backed up"
else
  echo "placeholder backup already present"
fi

# 2) 注入代理共享密钥（不允许在仓库内保存明文）
SECRET=$(grep -E '^AOJ_PROXY_SHARED_SECRET=' "$SH/backend.env" 2>/dev/null | head -1 | cut -d= -f2- || true)
if [ -z "${SECRET:-}" ]; then
  echo "AOJ_PROXY_SHARED_SECRET missing in $SH/backend.env" >&2
  exit 1
fi

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
sed "s|__AOJ_PROXY_SHARED_SECRET__|${SECRET}|g" "$TEMPLATE" > "$TMP"

# 3) 校验关键项后再落盘（上传上限必须是 200m）
if ! grep -qE '^[[:space:]]*client_max_body_size[[:space:]]+200m;' "$TMP"; then
  echo "template must set client_max_body_size 200m" >&2
  exit 1
fi

install -m 644 "$TMP" "$AVAIL"
ln -sfn "$AVAIL" "$SITE"
nginx -t
systemctl reload nginx
echo "nginx_reloaded template=$TEMPLATE"
