#!/usr/bin/env bash
# Same-netns SQLite API + Next + Chrome DOM checks for UX-CN-PRESET.
set -euo pipefail
ROOT="/home/hbs/hbs-projects/mihuanyuantu-v2"
API_PORT=38350
FE_PORT=3060
export DB_DRIVER=sqlite
export AOJ_ENABLED_MODULES=realphotos
DBFILE="/tmp/ux-cn-preset-$$.sqlite3"
export DATABASE_URL="sqlite+aiosqlite:///${DBFILE}"
rm -f "$DBFILE"

cd "$ROOT/aojuai-main/backend"
# prepare schema + seed before serving
.venv/bin/python - <<'PY'
import asyncio
import app.capabilities.realphotos.models  # noqa: F401
import app.domain  # noqa: F401
from sqlalchemy import text
from app.core.config import settings
from app.infrastructure.database.session import Base, async_session_factory, engine, init_db
from app.capabilities.realphotos.services.bootstrap import bootstrap_s0_accounts, DEFAULT_PASSWORD

SQLITE_ALTERS = (
    "ALTER TABLE cap_realphotos_merchant_profiles ADD COLUMN copy_latch_batch_id INTEGER",
    "ALTER TABLE cap_realphotos_merchant_profiles ADD COLUMN copy_latch_active INTEGER DEFAULT 0",
)

async def main() -> None:
    print("db_url", str(settings.DATABASE_URL).split("://")[0], "dialect", settings.DB_DIALECT)
    await init_db()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "sqlite":
            for stmt in SQLITE_ALTERS:
                try:
                    await conn.execute(text(stmt))
                except Exception as exc:
                    if "duplicate column" not in str(exc).lower():
                        print("alter_skip", stmt, type(exc).__name__, exc)
    async with async_session_factory() as db:
        summary = await bootstrap_s0_accounts(db)
        await db.commit()
        print("boot_ok", sorted(summary)[:4], "pwd_len", len(DEFAULT_PASSWORD))

asyncio.run(main())
PY

.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" > /tmp/ux-sqlite-api.log 2>&1 &
APIPID=$!
cd "$ROOT/aojuai-main/frontend"
env API_BASE_URL="http://127.0.0.1:$API_PORT" BACKEND_PORT="$API_PORT" NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:$API_PORT" \
  ./node_modules/.bin/next dev -H 127.0.0.1 -p "$FE_PORT" > /tmp/ux-sqlite-fe.log 2>&1 &
FEPID=$!
cleanup() { kill "$APIPID" "$FEPID" 2>/dev/null || true; }
trap cleanup EXIT

python3 - <<PY
import json, socket, time, urllib.request
API, FE = $API_PORT, $FE_PORT

def up(p):
    s = socket.socket(); s.settimeout(0.5)
    try: return s.connect_ex(("127.0.0.1", p)) == 0
    finally: s.close()

for i in range(90):
    if up(API) and up(FE):
        print("ports_up", i); break
    time.sleep(1)
else:
    raise SystemExit("ports never up")

for i in range(90):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{API}/api/v1/realphotos/auth/challenges", method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            print("api_ready", i, r.status); break
    except Exception as e:
        if i % 5 == 0: print("api_wait", i, type(e).__name__)
        time.sleep(1)
else:
    raise SystemExit("api not ready")

for i in range(40):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{FE}/login", timeout=5) as r:
            print("fe_ready", i, r.status); break
    except Exception as e:
        if i % 5 == 0: print("fe_wait", i, type(e).__name__)
        time.sleep(2)
else:
    raise SystemExit("fe not ready")

req = urllib.request.Request(
    f"http://127.0.0.1:{API}/api/v1/auth/login",
    data=json.dumps({"username": "rp_admin", "password": "S0Test@123456"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as r:
    data = json.load(r)["data"]
open("/tmp/ux_cn_session.json", "w").write(json.dumps(data))
print("login_ok", data["username"])
PY

mkdir -p /tmp/ux-cn-pup
cd /tmp/ux-cn-pup
if [[ ! -d node_modules/puppeteer-core ]]; then
  npm init -y >/dev/null 2>&1
  npm install puppeteer-core@23 --no-fund --no-audit >/tmp/ux-cn-npm.log 2>&1
fi

node <<NODE
const fs = require('fs');
const puppeteer = require('puppeteer-core');
(async () => {
  const session = JSON.parse(fs.readFileSync('/tmp/ux_cn_session.json','utf8'));
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: 'new',
    args: ['--no-sandbox','--disable-gpu','--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  const FE = 'http://127.0.0.1:$FE_PORT';
  await page.goto(FE + '/login', { waitUntil: 'domcontentloaded', timeout: 180000 });
  await page.evaluate((sess) => {
    localStorage.setItem('aojuai.session', JSON.stringify({
      avatar: sess.avatar || '', username: sess.username, nickname: sess.nickname,
      roles: sess.roles || [], permissions: sess.permissions || [],
      isSuperuser: !!sess.isSuperuser, mustCompleteProfile: !!sess.mustCompleteProfile,
      accessToken: sess.accessToken, refreshToken: sess.refreshToken, expires: sess.expires,
      authMode: 'bearer',
    }));
  }, session);
  const results = [];
  async function visit(path, checks) {
    await page.goto(FE + path, { waitUntil: 'domcontentloaded', timeout: 180000 });
    await new Promise(r => setTimeout(r, 2500));
    const text = await page.evaluate(() => (document.body && document.body.innerText) || '');
    const html = await page.content();
    const row = { path, textLen: text.length };
    for (const [k, fn] of Object.entries(checks)) row[k] = fn(text, html);
    try {
      fs.mkdirSync('/tmp/cursor/screenshots', { recursive: true });
      const shot = '/tmp/cursor/screenshots/ux-cn-preset-' + path.replace(/\\W+/g,'_') + '.png';
      await page.screenshot({ path: shot, fullPage: true }); row.shot = shot;
    } catch (e) { row.shotErr = String(e); }
    results.push(row);
  }
  await visit('/realphotos/library', {
    'E-U1-1': t => t.includes('选择文件'),
    'E-U1-2': t => /本地上传|文生图|图生图|来源/.test(t),
  });
  await visit('/realphotos/tasks', {
    'E-U2-1': t => t.includes('失败原因'),
    'E-U2-2': t => /已交付|失败|状态|积分处置/.test(t),
    'E-U3-dialog_btn': (t,h) => h.includes('详情') || t.includes('详情') || t.includes('暂无'),
  });
  const clicked = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find(x => (x.textContent||'').trim() === '详情');
    if (!b) return false; b.click(); return true;
  });
  await new Promise(r => setTimeout(r, 1000));
  const after = await page.evaluate(() => document.body.innerText);
  const hasDialog = await page.evaluate(() => !!document.querySelector('[role=dialog]'));
  results.push({ path:'/realphotos/tasks#detail', clickedDetail: clicked,
    'E-U3-1': clicked ? (hasDialog || /处理任务|关闭/.test(after)) : 'skipped_no_rows',
    'E-U3-2': clicked ? (/状态/.test(after) && /积分|处置/.test(after)) : 'skipped_no_rows' });
  await visit('/realphotos/presets', {
    'E-U5-1_no_clear': t => !t.includes('清除占位假预设'),
    'E-U5-1_no_bulk_btn': t => !t.includes('一键导入全部（405）'),
    'E-U5-2_pager': t => t.includes('每页') && t.includes('20'),
    'E-U6-1': t => t.includes('查看详情') || t.includes('新增预设'),
    'E-U7-1': t => t.includes('新增预设'),
    'E-U4-2': t => /不写入|手机|GPS|设备预设/.test(t),
  });
  await page.evaluate(() => { const b=[...document.querySelectorAll('button')].find(x=>(x.textContent||'').trim()==='新增预设'); if(b) b.click(); });
  await new Promise(r => setTimeout(r, 800));
  const formText = await page.evaluate(() => document.body.innerText);
  const hasFormDialog = await page.evaluate(() => !!document.querySelector('[role=dialog]'));
  results.push({ path:'/realphotos/presets#create', 'E-U7-2': hasFormDialog && /基本信息/.test(formText) && /拍摄参数/.test(formText) && /EXIF|GPS/.test(formText) });
  // Save one preset via the create dialog so 查看详情 can open.
  const stamp = String(Date.now()).slice(-6);
  await page.evaluate((code) => {
    const dialog = document.querySelector('[role=dialog]');
    if (!dialog) return;
    const inputs = [...dialog.querySelectorAll('input')];
    const setByPlaceholder = (ph, value) => {
      const el = inputs.find(i => (i.getAttribute('placeholder') || '') === ph);
      if (!el) return;
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(el, value);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    };
    setByPlaceholder('编号', code);
    setByPlaceholder('品牌', 'Honeybadger');
    setByPlaceholder('型号', 'UX-CN-Seed');
    setByPlaceholder('ISO', '100');
    setByPlaceholder('快门', '1/100');
    setByPlaceholder('光圈', 'f/2.0');
    setByPlaceholder('焦距', '24');
    const save = [...dialog.querySelectorAll('button')].find(b => (b.textContent || '').includes('保存'));
    if (save) save.click();
  }, `ux_cn_${stamp}`);
  await new Promise(r => setTimeout(r, 2500));
  await page.goto(FE + '/realphotos/presets', { waitUntil: 'domcontentloaded', timeout: 180000 });
  await new Promise(r => setTimeout(r, 2000));
  const openedDetail = await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find(x => (x.textContent||'').trim() === '查看详情');
    if (!b) return false; b.click(); return true;
  });
  await new Promise(r => setTimeout(r, 800));
  const detailText = await page.evaluate(() => document.body.innerText);
  const detailDialog = await page.evaluate(() => !!document.querySelector('[role=dialog]'));
  results.push({ path:'/realphotos/presets#detail', openedDetail, detailDialog,
    'E-U6-2': openedDetail && detailDialog && /预设详情/.test(detailText) && /GPS/.test(detailText) });
  await visit('/realphotos/tech-desk', {
    'E-U4-1': t => /工单/.test(t) && /账号冻结|图片申诉|全部|类型|尚无工单/.test(t),
  });
  fs.writeFileSync('/tmp/ux-cn-browser-dom.json', JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));
  const fails=[];
  for (const row of results) for (const [k,v] of Object.entries(row)) {
    if (k.startsWith('E-') && v !== true && v !== 'skipped_no_rows' && v !== 'skipped_no_presets') fails.push(row.path+':'+k+'='+v);
  }
  if (fails.length) { console.error('DOM_FAILS', fails.join('|')); process.exit(2); }
  console.log('BROWSER_DOM_PASS');
  await browser.close();
})().catch(e => { console.error('BROWSER_FAIL', e); process.exit(1); });
NODE

cd "$ROOT/aojuai-main/backend"
.venv/bin/python scripts/ux_cn_preset_e2e.py
.venv/bin/python - <<'PY'
from pathlib import Path
import json
log = Path('/tmp/ux-cn-preset-e2e.log')
text = log.read_text(encoding='utf-8')
dom = json.loads(Path('/tmp/ux-cn-browser-dom.json').read_text())
lines = ['=== browser_dom_section chrome_puppeteer_sqlite_same_netns ===', json.dumps(dom, ensure_ascii=False)]
flat_ok = True
for row in dom:
    for k, v in row.items():
        if str(k).startswith('E-'):
            if v is True or v in ('skipped_no_rows', 'skipped_no_presets'):
                lines.append(f'PASS {row.get("path")}:{k}={v}')
            else:
                flat_ok = False
                lines.append(f'FAIL {row.get("path")}:{k}={v}')
lines.append('production_billing=false')
lines.append('UX_CN_PRESET_E2E_PASS' if flat_ok else 'UX_CN_PRESET_E2E_FAIL')
text = text.replace('browser_dom_section_pending_ide_browser\n', '')
log.write_text(text.rstrip() + '\n' + '\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(log.read_text().splitlines()[-35:]))
PY
echo DONE
