"""Builds dashboard.html / card.html from riskmood data and renders PNGs with headless Chrome."""
import math, subprocess, os, html
ZONES = [(0, 25, "EXTREME|FEAR", "#ef4444"), (25, 45, "FEAR", "#f97316"), (45, 55, "NEUTRAL", "#eab308"), (55, 75, "GREED", "#84cc16"), (75, 100, "EXTREME|GREED", "#22c55e")]
COL = lambda s: next(c for lo, hi, _, c in ZONES if s < hi or hi == 100)

def spark(vals, w=220, h=50, color="#60a5fa", fill=True):
    lo, hi = min(vals), max(vals); r = (hi - lo) or 1
    pts = [(i * w / (len(vals) - 1), h - 4 - (v - lo) / r * (h - 8)) for i, v in enumerate(vals)]
    p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    gid = f"g{abs(hash(p))%10**6}"
    area = f'<polygon points="0,{h} {p} {w},{h}" fill="url(#{gid})"/>' if fill else ""
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none"><defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{color}" stop-opacity=".35"/><stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
            f'{area}<polyline points="{p}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'
            f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3" fill="{color}"/></svg>')

def gauge(score, size=420, updated=""):
    """CNN-style segmented gauge, dark theme."""
    cx, cy, R, r0 = 260, 262, 245, 152
    P = lambda v, rad: (cx + rad * math.cos(math.radians(180 - v * 1.8)), cy - rad * math.sin(math.radians(180 - v * 1.8)))
    out = []
    for lo, hi, txt, col in ZONES:
        act = lo <= score < hi or (hi == 100 and score >= 100)
        g = .5  # gap in score units
        a1, a2 = lo + (g if lo else 0), hi - (g if hi < 100 else 0)
        (x1, y1), (x2, y2), (x3, y3), (x4, y4) = P(a1, R), P(a2, R), P(a2, r0), P(a1, r0)
        big = 0
        out.append(f'<path d="M{x1:.1f},{y1:.1f} A{R},{R} 0 {big} 1 {x2:.1f},{y2:.1f} L{x3:.1f},{y3:.1f} A{r0},{r0} 0 {big} 0 {x4:.1f},{y4:.1f}Z" '
                   + (f'fill="{col}" fill-opacity=".28" stroke="{col}" stroke-width="2.5" filter="url(#zg)"' if act else 'fill="rgba(255,255,255,.055)" stroke="rgba(255,255,255,.08)"') + '/>')
        mid = (lo + hi) / 2; lines = txt.split("|"); rot = 90 - (180 - mid * 1.8)
        fs = 15 if len(lines) == 2 else (13 if hi - lo <= 10 else 17)
        for i, ln in enumerate(lines):
            tx, ty = P(mid, (R + r0) / 2 + (len(lines) - 1) * 9 - i * 19)
            out.append(f'<text x="{tx:.1f}" y="{ty:.1f}" transform="rotate({rot:.1f} {tx:.1f} {ty:.1f})" text-anchor="middle" dominant-baseline="middle" '
                       f'font-size="{fs}" font-weight="800" letter-spacing="1" fill="{"#fff" if act else "#64748b"}">{ln}</text>')
    for v in range(0, 101, 5):
        if v % 25:
            x, y = P(v, 136); out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2" fill="#64748b"/>')
        else:
            x, y = P(v, 128); out.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="15" fill="#94a3b8">{v}</text>')
    th = math.radians(180 - score * 1.8); ux, uy = math.cos(th), -math.sin(th); px, py = -uy, ux
    tip = (cx + ux * 150, cy + uy * 150); b1 = (cx + px * 11, cy + py * 11); b2 = (cx - px * 11, cy - py * 11)
    out.append(f'<polygon points="{tip[0]:.1f},{tip[1]:.1f} {b1[0]:.1f},{b1[1]:.1f} {b2[0]:.1f},{b2[1]:.1f}" fill="#f8fafc"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="46" fill="#0f172a" stroke="{COL(score)}" stroke-width="3"/>'
               f'<text x="{cx}" y="{cy+2}" text-anchor="middle" dominant-baseline="middle" font-size="38" font-weight="800" fill="#f8fafc">{score:.0f}</text>')
    if updated:
        out.append(f'<text x="14" y="{cy+48}" font-size="13" fill="#94a3b8">Last updated {updated}</text>')
    return (f'<svg viewBox="0 0 520 {cy+60 if updated else cy+50}" width="{size}" style="max-width:100%;height:auto"><defs><filter id="zg" x="-20%" y="-20%" width="140%" height="140%">'
            f'<feDropShadow dx="0" dy="0" stdDeviation="6" flood-opacity=".5"/></filter></defs>' + "".join(out) + "</svg>")

CSS = """*{box-sizing:border-box;margin:0}body{font-family:Inter,'Segoe UI',system-ui,sans-serif;color:#e2e8f0;
background:radial-gradient(circle at 15% 10%,#3b0764 0,transparent 40%),radial-gradient(circle at 90% 90%,#064e3b 0,transparent 45%),#070b17;}
.glass{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:20px;backdrop-filter:blur(14px);box-shadow:0 10px 40px rgba(0,0,0,.35)}
.muted{color:#94a3b8}.brand{font-weight:800;letter-spacing:-.5px;background:linear-gradient(90deg,#a78bfa,#60a5fa,#34d399);-webkit-background-clip:text;color:transparent}
.badge{display:inline-block;white-space:nowrap;padding:5px 12px;border-radius:999px;font-size:13px;font-weight:600}
.bar{height:7px;border-radius:9px;background:#1e293b;overflow:hidden}.bar>div{height:100%;border-radius:9px}"""

def cards(d, compact=False):
    out = ""
    for c in d["comps"]:
        col = COL(c["sub"]); up = c["chg_num"] >= 0
        out += f'''<div class="glass card"><div style="display:flex;justify-content:space-between;align-items:baseline">
<span class="muted" style="font-size:13px;text-transform:uppercase;letter-spacing:1px">{c["name"]}</span>
<span style="font-size:13px;color:{'#4ade80' if up else '#f87171'}">{'▲' if up else '▼'} {c["chg"]}</span></div>
<div style="font-size:{26 if compact else 30}px;font-weight:700;margin:6px 0 8px">{c["val"]}</div>
{'' if compact else spark(c["spark"], color="#60a5fa")}
<div style="display:flex;justify-content:space-between;font-size:12px;margin:8px 0 5px" class="muted"><span>{c["note"]}</span><span style="color:{col};font-weight:700">{c["sub"]:.0f}/100</span></div>
<div class="bar"><div style="width:{c["sub"]:.0f}%;background:{col}"></div></div>
<div style="font-size:11px;margin-top:7px;color:{'#4ade80' if c.get("live") else '#94a3b8'}">{c.get("asof_label","")}</div></div>'''
    return out

def upd():
    import datetime, zoneinfo
    n = datetime.datetime.now(zoneinfo.ZoneInfo("Pacific/Auckland"))
    return f"{n:%b %d} at {n:%H:%M} NZT"

def build(d):
    t, ch = d["score"], d["score"] - d["prev"]
    chc = "#4ade80" if ch >= 0 else "#f87171"
    divb = (f'<span class="badge" style="background:rgba(245,158,11,.18);color:#fbbf24;border:1px solid #f59e0b55">⚠ Divergence: sentiment {d["sent"]:.0f} vs prices {d["price"]:.0f}</span>'
            if d["div"] else f'<span class="badge" style="background:rgba(34,197,94,.12);color:#4ade80;border:1px solid #22c55e44">✓ Aligned: sentiment {d["sent"]:.0f} · prices {d["price"]:.0f}</span>')
    dash = f'''<!doctype html><html><head><meta charset="utf-8"><title>Risk Mood</title><style>{CSS}
body{{width:1200px;height:900px;padding:36px;display:flex;flex-direction:column}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-top:20px}}.card{{padding:18px}}</style></head><body>
<div style="display:flex;justify-content:space-between;align-items:center"><div><div class="brand" style="font-size:34px">Risk Mood</div>
<div class="muted" style="font-size:14px">Market sentiment × rates × tech × oil · as of US close {d["date"]}</div></div>{divb}</div>
<div style="display:grid;grid-template-columns:1.25fr 1fr;gap:18px;margin-top:22px;flex:1">
<div class="glass" style="padding:24px;text-align:center;display:flex;flex-direction:column;justify-content:center;align-items:center">{gauge(t, 460, upd())}
<div style="font-size:22px;font-weight:700;color:{COL(t)};margin-top:4px">{d["label"]}</div>
<div style="font-size:15px;margin-top:6px;color:{chc}">{'▲' if ch>=0 else '▼'} {abs(ch):.0f} vs yesterday ({d["prev"]:.0f})</div></div>
<div class="glass" style="padding:24px;display:flex;flex-direction:column;justify-content:space-between">
<div><div class="muted" style="font-size:13px;text-transform:uppercase;letter-spacing:1px">Why it moved</div>
<div style="font-size:18px;line-height:1.5;margin-top:10px">{html.escape(d["expl"])}</div></div>
<div><div class="muted" style="font-size:13px;text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px">30-day score</div>
{spark(d["trend"], w=440, h=110, color="#a78bfa")}<div class="muted" style="display:flex;justify-content:space-between;font-size:12px"><span>{d["trend_start"]}</span><span>{d["date"]}</span></div></div></div></div>
<div class="grid">{cards(d)}</div>
<div class="muted" style="font-size:11px;margin-top:18px">Data: Yahoo Finance (^VIX, ^TNX, ^IXIC, CL=F). Sentiment: {html.escape(d["src"])}. Sub-scores = 1-yr percentile ranks; 0 = extreme fear, 100 = extreme greed. Not financial advice.</div></body></html>'''
    card = f'''<!doctype html><html><head><meta charset="utf-8"><style>{CSS}
body{{width:1200px;height:675px;padding:40px 48px;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between}}.card{{padding:16px 18px}}</style></head><body>
<div style="display:flex;justify-content:space-between;align-items:center"><div class="brand" style="font-size:40px">Risk Mood</div>
<div style="display:flex;gap:12px;align-items:center">{('<span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80;border:1px solid #22c55e55">● Live</span>' if d.get("market")=="Live" else '<span class="badge" style="background:rgba(148,163,184,.12);color:#cbd5e1;border:1px solid #94a3b844">◐ US market closed</span>')}</div></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:center">
<div style="text-align:center">{gauge(t, 520, upd())}
<div style="font-size:28px;font-weight:700;color:{COL(t)}">{d["label"]} <span style="font-size:20px;color:{chc}">{'▲' if ch>=0 else '▼'}{abs(ch):.0f}</span></div></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">{cards(d, compact=True)}</div></div>
<div style="display:flex;justify-content:space-between;align-items:center"><div>{divb}</div>
<div class="muted" style="font-size:13px">0 = extreme fear · 100 = extreme greed · not financial advice</div></div></body></html>'''
    open("dashboard.html", "w").write(dash); open("card.html", "w").write(card)
    for name, w, h in (("dashboard", 1200, 900), ("card", 1200, 675)):
        subprocess.run([os.environ.get("CHROME","google-chrome"), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        f"--window-size={w},{h}", f"--screenshot={os.path.abspath(name + '.png')}",
                        "file://" + os.path.abspath(name + ".html")], capture_output=True, timeout=60)


def build_site(d, out="site"):
    """Responsive live page + card.png + data.json for GitHub Pages."""
    import json, datetime, zoneinfo, shutil
    os.makedirs(out, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc)
    nz = now.astimezone(zoneinfo.ZoneInfo("Pacific/Auckland"))
    t, ch = d["score"], d["score"] - d["prev"]; chc = "#4ade80" if ch >= 0 else "#f87171"
    divb = (f'<span class="badge" style="background:rgba(245,158,11,.18);color:#fbbf24;border:1px solid #f59e0b55">⚠ Divergence: sentiment {d["sent"]:.0f} vs prices {d["price"]:.0f}</span>'
            if d["div"] else f'<span class="badge" style="background:rgba(34,197,94,.12);color:#4ade80;border:1px solid #22c55e44">✓ Aligned: sentiment {d["sent"]:.0f} · prices {d["price"]:.0f}</span>')
    url = "https://samnaus.github.io/risk-mood/"
    desc = f"Risk Mood {t:.0f}/100 ({d['label']}, {ch:+.0f}) - one score for VIX, 10Y yield, Nasdaq and oil."
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Risk Mood: {t:.0f} {d["label"]}</title><meta name="description" content="{html.escape(desc)}">
<meta property="og:type" content="website"><meta property="og:url" content="{url}"><meta property="og:title" content="Risk Mood: {t:.0f}/100 {d["label"]}">
<meta property="og:description" content="{html.escape(desc)}"><meta property="og:image" content="{url}card.png?v={int(now.timestamp())}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="675">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="Risk Mood: {t:.0f}/100 {d["label"]}">
<meta name="twitter:description" content="{html.escape(desc)}"><meta name="twitter:image" content="{url}card.png?v={int(now.timestamp())}">
<meta http-equiv="refresh" content="900"><style>{CSS}
body{{min-height:100vh;padding:clamp(18px,4vw,48px)}}.wrap{{max-width:1150px;margin:0 auto}}
.top{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}}
.main{{display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:center;margin:28px 0}}
.cards{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.card{{padding:16px 18px}}
.gauge svg{{width:100%;max-width:500px;height:auto}}.score{{font-size:clamp(64px,12vw,104px);font-weight:800;line-height:1}}
.foot{{display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px;align-items:center;font-size:13px}}
@media(max-width:820px){{.main{{grid-template-columns:1fr}}}}@media(max-width:420px){{.cards{{grid-template-columns:1fr}}}}</style></head><body><div class="wrap">
<div class="top"><div class="brand" style="font-size:clamp(30px,5vw,44px)">Risk Mood</div><div style="display:flex;gap:10px;align-items:center">{('<span class="badge" style="background:rgba(34,197,94,.15);color:#4ade80;border:1px solid #22c55e55">● Live</span>' if d.get("market")=="Live" else '<span class="badge" style="background:rgba(148,163,184,.12);color:#cbd5e1;border:1px solid #94a3b844">◐ US market closed</span>')}<span class="muted">as of {nz:%a %d %b, %H:%M} NZT</span></div></div>
<div class="main"><div class="gauge" style="text-align:center">{gauge(t, 520, upd())}
<div style="font-size:28px;font-weight:700;color:{COL(t)}">{d["label"]} <span style="font-size:20px;color:{chc}">{'▲' if ch>=0 else '▼'}{abs(ch):.0f}</span></div>
<div class="muted" style="font-size:14px;margin-top:4px">vs {d["prev"]:.0f} at prior session close</div></div>
<div class="cards">{cards(d, compact=True)}</div></div>
<div class="glass" style="padding:18px 20px;margin-bottom:18px"><div class="muted" style="font-size:12px;text-transform:uppercase;letter-spacing:1px">Why it moved</div>
<div style="font-size:16px;line-height:1.5;margin-top:6px">{html.escape(d["expl"])}</div></div>
<div class="foot"><div>{divb}</div><div class="muted">Last updated {nz:%a %d %b %Y, %H:%M} NZT · {now:%Y-%m-%d %H:%M} UTC</div></div>
<p class="muted" style="font-size:12px;margin-top:16px;line-height:1.6">Data: Yahoo Finance (^VIX, ^TNX, ^IXIC, CL=F). Sentiment: {html.escape(d["src"])}.
Sub-scores are 1-year percentile ranks; 0 = extreme fear, 100 = extreme greed. Refreshes about every 15 minutes; prices are the latest 1-minute quotes (Yahoo data can be delayed ~15 min; ^TNX has no pre/after-market quotes); changes are vs previous close. Not financial advice. <a href="data.json" style="color:#60a5fa">data.json</a></p>
</div></body></html>'''
    open(os.path.join(out, "index.html"), "w").write(page)
    shutil.copy("card.png", os.path.join(out, "card.png"))
    dj = {k: v for k, v in d.items() if k != "trend"}
    for c in dj["comps"]: c.pop("spark", None)
    dj.update(market=d.get("market"), updated_utc=now.isoformat(timespec="seconds"), updated_nz=nz.isoformat(timespec="seconds"), trend_30d=d["trend"])
    json.dump(dj, open(os.path.join(out, "data.json"), "w"), indent=2)
    open(os.path.join(out, ".nojekyll"), "w").close()
