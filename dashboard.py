"""Builds dashboard.html / card.html from riskmood data and renders PNGs with headless Chrome."""
import math, subprocess, os, html
COL = lambda s: "#ef4444" if s < 40 else ("#f59e0b" if s < 60 else "#22c55e")

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

def gauge(score, size=420):
    cx, cy, r = 210, 210, 170
    a = math.radians(180 - score * 1.8)
    nx, ny = cx + (r - 30) * math.cos(a), cy - (r - 30) * math.sin(a)
    ticks = "".join(f'<text x="{cx+(r+22)*math.cos(math.radians(180-t*1.8)):.0f}" y="{cy-(r+22)*math.sin(math.radians(180-t*1.8))+4:.0f}" '
                    f'fill="#94a3b8" font-size="12" text-anchor="middle">{t}</text>' for t in (0, 25, 50, 75, 100))
    return f'''<svg viewBox="0 0 420 228" width="{size}">
<defs><linearGradient id="gg" x1="0" x2="1"><stop offset="0" stop-color="#dc2626"/><stop offset=".3" stop-color="#f97316"/>
<stop offset=".5" stop-color="#f59e0b"/><stop offset=".7" stop-color="#84cc16"/><stop offset="1" stop-color="#16a34a"/></linearGradient>
<filter id="gl"><feGaussianBlur stdDeviation="6"/></filter></defs>
<path d="M{cx-r},{cy} A{r},{r} 0 0 1 {cx+r},{cy}" stroke="#1e293b" stroke-width="30" fill="none" stroke-linecap="round"/>
<path d="M{cx-r},{cy} A{r},{r} 0 0 1 {cx+r},{cy}" stroke="url(#gg)" stroke-width="30" fill="none" stroke-linecap="round" opacity=".35" filter="url(#gl)"/>
<path d="M{cx-r},{cy} A{r},{r} 0 0 1 {cx+r},{cy}" stroke="url(#gg)" stroke-width="22" fill="none" stroke-linecap="round"/>
{ticks}
<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#f8fafc" stroke-width="5" stroke-linecap="round"/>
<circle cx="{cx}" cy="{cy}" r="13" fill="#f8fafc"/><circle cx="{cx}" cy="{cy}" r="6" fill="#0f172a"/></svg>'''

CSS = """*{box-sizing:border-box;margin:0}body{font-family:Inter,'Segoe UI',system-ui,sans-serif;color:#e2e8f0;
background:radial-gradient(circle at 15% 10%,#3b0764 0,transparent 40%),radial-gradient(circle at 90% 90%,#064e3b 0,transparent 45%),#070b17;}
.glass{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:20px;backdrop-filter:blur(14px);box-shadow:0 10px 40px rgba(0,0,0,.35)}
.muted{color:#94a3b8}.brand{font-weight:800;letter-spacing:-.5px;background:linear-gradient(90deg,#a78bfa,#60a5fa,#34d399);-webkit-background-clip:text;color:transparent}
.badge{display:inline-block;padding:5px 12px;border-radius:999px;font-size:13px;font-weight:600}
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
<div class="bar"><div style="width:{c["sub"]:.0f}%;background:{col}"></div></div></div>'''
    return out

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
<div class="glass" style="padding:24px;text-align:center;display:flex;flex-direction:column;justify-content:center;align-items:center">{gauge(t)}
<div style="margin-top:4px;font-size:76px;font-weight:800;line-height:1">{t:.0f}</div>
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
<div class="muted" style="font-size:18px">US close · {d["date"]}</div></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:36px;align-items:center">
<div style="text-align:center">{gauge(t, 500)}<div style="margin-top:6px;font-size:96px;font-weight:800;line-height:1">{t:.0f}</div>
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
<div class="top"><div class="brand" style="font-size:clamp(30px,5vw,44px)">Risk Mood</div><div class="muted">US close · {d["date"]}</div></div>
<div class="main"><div class="gauge" style="text-align:center">{gauge(t,500)}<div class="score">{t:.0f}</div>
<div style="font-size:28px;font-weight:700;color:{COL(t)}">{d["label"]} <span style="font-size:20px;color:{chc}">{'▲' if ch>=0 else '▼'}{abs(ch):.0f}</span></div>
<div class="muted" style="font-size:14px;margin-top:4px">vs {d["prev"]:.0f} previous close</div></div>
<div class="cards">{cards(d, compact=True)}</div></div>
<div class="glass" style="padding:18px 20px;margin-bottom:18px"><div class="muted" style="font-size:12px;text-transform:uppercase;letter-spacing:1px">Why it moved</div>
<div style="font-size:16px;line-height:1.5;margin-top:6px">{html.escape(d["expl"])}</div></div>
<div class="foot"><div>{divb}</div><div class="muted">Last updated {nz:%a %d %b %Y, %H:%M} NZT · {now:%Y-%m-%d %H:%M} UTC</div></div>
<p class="muted" style="font-size:12px;margin-top:16px;line-height:1.6">Data: Yahoo Finance (^VIX, ^TNX, ^IXIC, CL=F). Sentiment: {html.escape(d["src"])}.
Sub-scores are 1-year percentile ranks; 0 = extreme fear, 100 = extreme greed. Refreshes about every 15 minutes; values reflect the latest day with all four inputs. Not financial advice. <a href="data.json" style="color:#60a5fa">data.json</a></p>
</div></body></html>'''
    open(os.path.join(out, "index.html"), "w").write(page)
    shutil.copy("card.png", os.path.join(out, "card.png"))
    dj = {k: v for k, v in d.items() if k != "trend"}
    for c in dj["comps"]: c.pop("spark", None)
    dj.update(updated_utc=now.isoformat(timespec="seconds"), updated_nz=nz.isoformat(timespec="seconds"), trend_30d=d["trend"])
    json.dump(dj, open(os.path.join(out, "data.json"), "w"), indent=2)
    open(os.path.join(out, ".nojekyll"), "w").close()
