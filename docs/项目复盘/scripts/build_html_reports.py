#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 docs/项目复盘 下 01/02/03 .md 转为离线自包含 .html（蜜獾原图气质，无外部 CDN）。"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV_PATH = ROOT / "evidence_metrics.json"
EV = json.loads(EV_PATH.read_text(encoding="utf-8")) if EV_PATH.exists() else {}

CSS = """
:root{
  --ink:#17202c;--ink-soft:#314052;--muted:#6f7a86;
  --paper:#f5f3ee;--panel:#fff;--line:#dde3e5;
  --teal:#1aa89a;--teal-deep:#0e766d;--amber:#f3be5a;--coral:#ee8066;
  --sidebar:#101924;--sidebar-soft:#1c2a39;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --sans:Inter,"PingFang SC","Microsoft YaHei",sans-serif;
  --display:"Noto Serif SC","Songti SC",Georgia,serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:var(--sans);color:var(--ink);background:var(--paper);line-height:1.65}
a{color:var(--teal-deep);text-decoration:none}
a:hover{text-decoration:underline}
.layout{display:grid;grid-template-columns:270px 1fr;min-height:100vh}
.sidebar{position:sticky;top:0;height:100vh;overflow:auto;background:var(--sidebar);color:#e8eef4;padding:20px 16px}
.sidebar .brand{font-family:var(--display);font-size:1.05rem;color:var(--amber);margin:0 0 4px}
.sidebar h1{font-size:.95rem;margin:0 0 8px;line-height:1.35;color:#fff;font-weight:600}
.sidebar .meta{font-size:.72rem;opacity:.8;margin-bottom:12px;color:#b7c4d2}
.sidebar input{width:100%;padding:8px 10px;border-radius:10px;border:1px solid #2a3a4c;background:var(--sidebar-soft);color:#fff;margin-bottom:12px}
.sidebar nav a{display:block;color:#c9d6e4;padding:6px 8px;border-radius:8px;font-size:.84rem;margin:2px 0}
.sidebar nav a:hover{background:#243447;text-decoration:none;color:#fff}
.sidebar nav a.h2{font-weight:600;color:#fff}
.sidebar nav a.h3{padding-left:16px;font-size:.78rem;opacity:.9}
.sidebar .navlinks{margin-top:16px;padding-top:12px;border-top:1px solid #2a3a4c;font-size:.8rem}
.sidebar .navlinks a{color:var(--amber)}
.main{padding:28px 36px 64px;max-width:1080px}
.hero{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:22px 24px;margin-bottom:22px;box-shadow:0 12px 36px rgba(18,34,51,.06)}
.hero .eyebrow{color:var(--teal-deep);font-size:.78rem;font-weight:600;letter-spacing:.04em;margin:0 0 6px}
.hero h1{margin:0 0 8px;font-size:1.65rem;font-family:var(--display);color:var(--ink)}
.badges{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 0}
.badge{display:inline-flex;padding:4px 10px;border-radius:999px;background:#eef8f6;color:var(--teal-deep);font-size:.76rem;border:1px solid #c9e8e3}
.badge.amber{background:#fff6e5;color:#8a6a1a;border-color:#f0d9a0}
.content h2{margin-top:2rem;padding-top:.5rem;border-top:1px solid var(--line);color:var(--ink);font-size:1.28rem;font-family:var(--display)}
.content h3{color:var(--ink-soft);margin-top:1.35rem;font-size:1.05rem}
.content p,.content li{font-size:.95rem}
.content table{width:100%;border-collapse:collapse;margin:12px 0 18px;font-size:.86rem;background:var(--panel)}
.content th,.content td{border:1px solid var(--line);padding:8px 10px;vertical-align:top;text-align:left}
.content th{background:#eef6f4;color:var(--teal-deep)}
.content tr:nth-child(even) td{background:#fafbf9}
.content code{font-family:var(--mono);font-size:.84em;background:#eef2f4;padding:1px 5px;border-radius:4px}
.content pre{background:#101924;color:#e7eef7;padding:14px 16px;border-radius:12px;overflow:auto;font-family:var(--mono);font-size:.78rem;line-height:1.5}
.content blockquote{margin:12px 0;padding:10px 14px;border-left:4px solid var(--teal);background:#f0f7f5;color:var(--muted)}
.content hr{border:none;border-top:1px solid var(--line);margin:24px 0}
.content ul{padding-left:1.2rem}
.arch{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin:16px 0}
.arch svg{width:100%;height:auto;display:block}
.footer{margin-top:40px;color:var(--muted);font-size:.82rem}
@media (max-width:960px){.layout{grid-template-columns:1fr}.sidebar{position:relative;height:auto}.main{padding:18px}}
@media print{
  body{background:#fff}.sidebar{display:none}.layout{display:block}.main{max-width:none;padding:0}
  a{color:inherit;text-decoration:none}.content h2{break-before:page}.content h2:first-of-type{break-before:auto}
}
"""

ARCH_SVG = """
<svg viewBox="0 0 960 460" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="蜜獾原图系统架构图">
  <rect width="960" height="460" fill="#f8faf9"/>
  <rect x="40" y="24" width="880" height="64" rx="14" fill="#101924"/>
  <text x="480" y="52" text-anchor="middle" fill="#f3be5a" font-size="16" font-family="Segoe UI, Microsoft YaHei, sans-serif">Browser · Next.js / React · realphotos 角色菜单</text>
  <text x="480" y="74" text-anchor="middle" fill="#9fb0c0" font-size="12" font-family="Segoe UI, Microsoft YaHei, sans-serif">HTTPS · exif-demo.honeybadgersoft.com</text>
  <rect x="400" y="100" width="160" height="36" rx="10" fill="#1aa89a"/>
  <text x="480" y="123" text-anchor="middle" fill="#fff" font-size="13" font-family="Segoe UI, Microsoft YaHei, sans-serif">Nginx + TLS</text>
  <rect x="40" y="154" width="880" height="110" rx="14" fill="#0e766d"/>
  <text x="480" y="188" text-anchor="middle" fill="#fff" font-size="15" font-family="Segoe UI, Microsoft YaHei, sans-serif">FastAPI · aojuai + capability realphotos</text>
  <text x="480" y="214" text-anchor="middle" fill="#d7f3ee" font-size="12" font-family="Segoe UI, Microsoft YaHei, sans-serif">会话/RBAC · 积分流水 · 任务批次检测 · 生图 · 业务 API · 受控网关 · 运营台</text>
  <text x="480" y="238" text-anchor="middle" fill="#d7f3ee" font-size="12" font-family="Segoe UI, Microsoft YaHei, sans-serif">供应商合同（duty）· OpenAPI</text>
  <rect x="80" y="292" width="360" height="70" rx="12" fill="#17202c"/>
  <text x="260" y="322" text-anchor="middle" fill="#fff" font-size="14" font-family="Segoe UI, Microsoft YaHei, sans-serif">PostgreSQL</text>
  <text x="260" y="344" text-anchor="middle" fill="#9fb0c0" font-size="12" font-family="Segoe UI, Microsoft YaHei, sans-serif">任务队列 · 账本 · 业务表</text>
  <rect x="520" y="292" width="360" height="70" rx="12" fill="#314052"/>
  <text x="700" y="322" text-anchor="middle" fill="#fff" font-size="14" font-family="Segoe UI, Microsoft YaHei, sans-serif">LocalDisk + 网关</text>
  <text x="700" y="344" text-anchor="middle" fill="#c9d6e4" font-size="12" font-family="Segoe UI, Microsoft YaHei, sans-serif">upload / phy-export / export · 禁裸路径</text>
  <rect x="140" y="386" width="680" height="48" rx="12" fill="#1c2a39"/>
  <text x="480" y="416" text-anchor="middle" fill="#e8eef4" font-size="13" font-family="Segoe UI, Microsoft YaHei, sans-serif">process / notify / cleanup workers · 预审 · 生图 · 文本 · Gemini 检测 · 导入</text>
</svg>
"""


def slugify(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text)
    s = re.sub(r"[^\w\u4e00-\u9fff\- ]+", "", s).strip()
    s = re.sub(r"\s+", "-", s)
    return s[:80] or "sec"


def inline_md(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def md_to_html_body(md: str) -> tuple[str, list[tuple[str, str, str]]]:
    lines = md.splitlines()
    out: list[str] = []
    toc: list[tuple[str, str, str]] = []
    i = 0
    in_code = False
    code_buf: list[str] = []
    in_ul = False
    table_buf: list[str] = []

    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    def flush_table():
        nonlocal table_buf
        if not table_buf:
            return
        rows = []
        for raw in table_buf:
            cells = [c.strip() for c in raw.strip().strip("|").split("|")]
            rows.append(cells)
        if len(rows) >= 2 and all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in rows[1]):
            header, body = rows[0], rows[2:]
        else:
            header, body = rows[0], rows[1:]
        out.append("<table><thead><tr>" + "".join(f"<th>{inline_md(c)}</th>" for c in header) + "</tr></thead><tbody>")
        for r in body:
            while len(r) < len(header):
                r.append("")
            out.append("<tr>" + "".join(f"<td>{inline_md(c)}</td>" for c in r[: len(header)]) + "</tr>")
        out.append("</tbody></table>")
        table_buf = []

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            close_ul()
            flush_table()
            if not in_code:
                in_code = True
                code_buf = []
            else:
                out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
                in_code = False
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        if line.strip().startswith("|") and "|" in line.strip()[1:]:
            close_ul()
            table_buf.append(line)
            i += 1
            continue
        else:
            flush_table()

        if line.startswith("# "):
            close_ul()
            # skip document H1 in body; used as hero
            i += 1
            continue
        m = re.match(r"^(#{2,4})\s+(.*)$", line)
        if m:
            close_ul()
            level = len(m.group(1))
            title = m.group(2).strip()
            sid = slugify(title)
            toc.append((f"h{level}", sid, title))
            out.append(f'<h{level} id="{html.escape(sid)}">{inline_md(title)}</h{level}>')
            if "逻辑架构" in title:
                out.append(f'<div class="arch">{ARCH_SVG}</div>')
            i += 1
            continue
        if line.strip() == "---":
            close_ul()
            out.append("<hr/>")
            i += 1
            continue
        if line.startswith("> "):
            close_ul()
            out.append(f"<blockquote><p>{inline_md(line[2:])}</p></blockquote>")
            i += 1
            continue
        if re.match(r"^[-*]\s+", line):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline_md(re.sub(r'^[-*]\\s+', '', line))}</li>")
            i += 1
            continue
        if re.match(r"^\d+\.\s+", line):
            close_ul()
            # keep as paragraph list items in ol-like paragraphs for simplicity
            if not out or not out[-1].startswith("<ol"):
                out.append("<ol>")
            out.append(f"<li>{inline_md(re.sub(r'^\\d+\\.\\s+', '', line))}</li>")
            # peek
            j = i + 1
            while j < len(lines) and re.match(r"^\d+\.\s+", lines[j]):
                out.append(f"<li>{inline_md(re.sub(r'^\\d+\\.\\s+', '', lines[j]))}</li>")
                j += 1
            out.append("</ol>")
            i = j
            continue
        if not line.strip():
            close_ul()
            i += 1
            continue
        close_ul()
        out.append(f"<p>{inline_md(line)}</p>")
        i += 1
    close_ul()
    flush_table()
    return "\n".join(out), toc


def extract_title(md: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "蜜獾原图复盘"


def render_page(md_name: str, html_name: str, eyebrow: str) -> None:
    md = (ROOT / md_name).read_text(encoding="utf-8")
    title = extract_title(md)
    body, toc = md_to_html_body(md)
    git = EV.get("git", {})
    badges = [
        f'<span class="badge">HEAD {html.escape(str(git.get("head_short", "n/a")))}</span>',
        f'<span class="badge">commits {html.escape(str(git.get("commit_count", "n/a")))}</span>',
        f'<span class="badge">PRs {html.escape(str(EV.get("pull_requests", {}).get("merged_into_main", "n/a")))}</span>',
        '<span class="badge amber">production_billing=false</span>',
    ]
    nav = []
    for level, sid, t in toc:
        nav.append(f'<a class="{level}" href="#{html.escape(sid)}">{html.escape(t)}</a>')
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="brand">蜜獾原图 v2</div>
  <h1>{html.escape(title)}</h1>
  <div class="meta">离线文档 · 双击即可打开 · 支持打印 PDF</div>
  <input id="q" type="search" placeholder="过滤目录…" oninput="filterNav(this.value)"/>
  <nav id="toc">{''.join(nav)}</nav>
  <div class="navlinks">
    <a href="index.html">← 总览门户</a><br/>
    <a href="01_开发会话复盘与成败经验.html">01 复盘</a><br/>
    <a href="02_项目架构与开发路线图.html">02 架构</a><br/>
    <a href="03_后续优化与演进建议.html">03 演进</a>
  </div>
</aside>
<main class="main">
  <header class="hero">
    <p class="eyebrow">{html.escape(eyebrow)}</p>
    <h1>{html.escape(title)}</h1>
    <div class="badges">{''.join(badges)}</div>
  </header>
  <article class="content">
{body}
  </article>
  <p class="footer">由 Markdown 生成 · 证据见 evidence_metrics.json / pr_stage_map.json · 公网 https://exif-demo.honeybadgersoft.com</p>
</main>
</div>
<script>
function filterNav(q){{
  q=(q||'').toLowerCase();
  document.querySelectorAll('#toc a').forEach(a=>{{
    a.style.display=!q||a.textContent.toLowerCase().includes(q)?'block':'none';
  }});
}}
</script>
</body>
</html>
"""
    (ROOT / html_name).write_text(page, encoding="utf-8")
    print("wrote", html_name)


def render_index() -> None:
    git = EV.get("git", {})
    pr = EV.get("pull_requests", {})
    product = EV.get("product", {})
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>蜜獾原图 v2 · 项目复盘门户</title>
<style>{CSS}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-top:18px}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 10px 28px rgba(18,34,51,.05)}}
.card h2{{margin:0 0 8px;font-size:1.05rem;font-family:var(--display)}}
.card p{{margin:0;color:var(--muted);font-size:.88rem}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-top:16px}}
.stat{{background:#eef8f6;border:1px solid #c9e8e3;border-radius:12px;padding:12px}}
.stat b{{display:block;font-size:1.2rem;color:var(--teal-deep)}}
.stat span{{font-size:.75rem;color:var(--muted)}}
</style>
</head>
<body>
<div class="layout">
<aside class="sidebar">
  <div class="brand">蜜獾原图 v2</div>
  <h1>项目复盘门户</h1>
  <div class="meta">Markdown + HTML · 内部讲述用</div>
  <nav>
    <a class="h2" href="01_开发会话复盘与成败经验.html">01 开发过程复盘</a>
    <a class="h2" href="02_项目架构与开发路线图.html">02 架构与路线图</a>
    <a class="h2" href="03_后续优化与演进建议.html">03 产品演进建议</a>
    <a class="h2" href="README.md">README.md</a>
  </nav>
</aside>
<main class="main">
  <header class="hero">
    <p class="eyebrow">PROJECT RETROSPECTIVE</p>
    <h1>蜜獾原图 v2 · 项目复盘</h1>
    <p style="margin:8px 0 0;color:var(--muted)">公网入口：<a href="https://exif-demo.honeybadgersoft.com">https://exif-demo.honeybadgersoft.com</a></p>
    <div class="stats">
      <div class="stat"><b>{html.escape(str(git.get("commit_count","—")))}</b><span>origin/main 提交</span></div>
      <div class="stat"><b>{html.escape(str(pr.get("merged_into_main","—")))}</b><span>已合入 PR</span></div>
      <div class="stat"><b>{html.escape(str((git.get("tags") or ["—"])[0] if isinstance(git.get("tags"), list) else git.get("tags","—")))}</b><span>最近 Tag</span></div>
      <div class="stat"><b>{html.escape(str(git.get("head_short","—")))}</b><span>HEAD short</span></div>
      <div class="stat"><b>{"false" if product.get("production_billing") is False else html.escape(str(product.get("production_billing","—")))}</b><span>production_billing</span></div>
    </div>
  </header>
  <div class="cards">
    <a class="card" href="01_开发会话复盘与成败经验.html"><h2>01 开发过程复盘</h2><p>九章演进、成功经验、失败教训与 SOP。</p></a>
    <a class="card" href="02_项目架构与开发路线图.html"><h2>02 架构与路线图</h2><p>逻辑架构、子系统与 Past/Future 路线。</p></a>
    <a class="card" href="03_后续优化与演进建议.html"><h2>03 产品演进建议</h2><p>仅现行部署仍存在的产品缺口（P0/P1/P2）。</p></a>
  </div>
  <p class="footer">证据：evidence_metrics.json · pr_stage_map.json · 仅已合入 main 的事实</p>
</main>
</div>
</body>
</html>
"""
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    print("wrote index.html")


def main() -> None:
    render_page("01_开发会话复盘与成败经验.md", "01_开发会话复盘与成败经验.html", "开发过程复盘 · 成败经验")
    render_page("02_项目架构与开发路线图.md", "02_项目架构与开发路线图.html", "架构全景 · 开发路线图")
    render_page("03_后续优化与演进建议.md", "03_后续优化与演进建议.html", "产品优化 · 现行不足")
    render_index()


if __name__ == "__main__":
    main()
