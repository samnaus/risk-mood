#!/usr/bin/env python3
"""Risk Mood: a free-data replica of CNN's Fear & Greed method.
7 equally weighted indicators, each scored 0-100 by how far it sits from its 2-year average
relative to its normal (std-dev) range: score = 100 * NormalCDF(z), then averaged.
Run: python riskmood.py   (writes site/, card.png, dashboard.html, chart.png, xpost.txt)"""
import io, math, urllib.request, pandas as pd, numpy as np, yfinance as yf
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

NORM = 504          # ~2 trading years for mean/std (CNN/TheStreet: "relative to the last two years")
FRESH = pd.Timedelta(minutes=20)
NOW = pd.Timestamp.now(tz="UTC")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"}
Phi = lambda z: 0.5 * (1 + np.vectorize(math.erf)(z / math.sqrt(2)))

# ---------- data ----------
IDX = ["^GSPC", "^VIX", "^VIX3M", "SPY", "TLT"]
daily = yf.download(IDX, period="4y", progress=False, auto_adjust=True)["Close"]
daily.index = pd.to_datetime(daily.index).tz_localize(None).normalize()

LIVE, cols = {}, {}
for tk in IDX:
    s = daily[tk].dropna()
    try:
        h = yf.Ticker(tk).history(period="5d", interval="1m", prepost=True)["Close"].dropna()
        px, ts = float(h.iloc[-1]), h.index[-1]; day = pd.Timestamp(ts.date())
        prev = float(s[s.index < day].iloc[-1]); s = s[s.index < day]; s.loc[day] = px
        LIVE[tk] = dict(price=px, prev_close=prev, asof=ts.tz_convert("UTC"), live=bool(NOW - ts.tz_convert("UTC") < FRESH), src="1-min quote")
    except Exception as e:
        LIVE[tk] = dict(price=float(s.iloc[-1]), prev_close=float(s.iloc[-2]), asof=s.index[-1].tz_localize("UTC") + pd.Timedelta(hours=20),
                        live=False, src=f"daily close ({type(e).__name__})")
    cols[tk] = s.sort_index()
px = pd.DataFrame(cols).ffill().dropna()

# S&P 500 members (current list, survivorship bias acknowledged) for highs/lows + volume breadth
mem = pd.read_csv("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv")
tks = [t.replace(".", "-") for t in mem.Symbol]
m = yf.download(tks, period="4y", progress=False, auto_adjust=True, threads=True)
mc, mv = m["Close"], m["Volume"]
mc.index = mv.index = pd.to_datetime(mc.index).tz_localize(None).normalize()
mc = mc[mc.count(axis=1) > 0.9 * len(tks)]; mv = mv.loc[mc.index]
hi52, lo52 = mc.rolling(252, min_periods=240).max(), mc.rolling(252, min_periods=240).min()
valid = hi52.notna()
nh = ((mc >= hi52) & valid).sum(axis=1); nl = ((mc <= lo52) & valid).sum(axis=1)
strength = ((nh - nl) / valid.sum(axis=1).replace(0, np.nan) * 100).dropna()           # net new highs, % of members
chg = mc.diff()
upv, dnv = mv.where(chg > 0, 0).sum(axis=1), mv.where(chg < 0, 0).sum(axis=1)
net = ((upv - dnv) / (upv + dnv) * 1000).iloc[1:]
osc = net.ewm(alpha=0.10, adjust=False).mean() - net.ewm(alpha=0.05, adjust=False).mean()   # McClellan 19/39 EMA
breadth = osc.cumsum()                                                              # Volume Summation Index
memb_asof = mc.index[-1]

# Junk vs investment-grade spread (ICE BofA OAS via FRED, no key)
def fred():
    url = ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2,BAMLC0A0CM&cosd="
           + (NOW - pd.Timedelta(days=1500)).strftime("%Y-%m-%d"))
    for i in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "curl/8.5.0"}), timeout=30).read().decode()
        except Exception as e: err = e
    raise err
fr = pd.read_csv(io.StringIO(fred()), index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce").dropna()
junk = (fr["BAMLH0A0HYM2"] - fr["BAMLC0A0CM"])

# ---------- indicators (raw series; sign: + = greed) ----------
g = px["^GSPC"]
RAW = {
    "momentum": (g / g.rolling(125).mean() - 1) * 100,
    "strength": strength,
    "breadth": breadth,
    "putcall": (px["^VIX"] / px["^VIX3M"]).rolling(5).mean(),
    "volatility": (px["^VIX"] / px["^VIX"].rolling(50).mean() - 1) * 100,
    "safehaven": (px["SPY"].pct_change(20) - px["TLT"].pct_change(20)) * 100,
    "junk": junk,
}
SIGN = {"momentum": 1, "strength": 1, "breadth": 1, "putcall": -1, "volatility": -1, "safehaven": 1, "junk": -1}
idx = px.index
sub, rawa = pd.DataFrame(index=idx), pd.DataFrame(index=idx)
for k, s in RAW.items():
    s = s.dropna()
    z = (s - s.rolling(NORM, min_periods=250).mean()) / s.rolling(NORM, min_periods=250).std()
    sc = pd.Series(100 * Phi(SIGN[k] * z.values), index=z.index).where(z.notna())
    sub[k] = sc.reindex(idx.union(sc.index)).ffill().reindex(idx)
    rawa[k] = s.reindex(idx.union(s.index)).ffill().reindex(idx)
sub = sub.dropna(); rawa = rawa.loc[sub.index]
score = sub.mean(axis=1)
senti = sub[["putcall", "volatility"]].mean(axis=1); price = sub.drop(columns=["putcall", "volatility"]).mean(axis=1)
div = (senti - price).abs() > 25
score, sub, senti, price, div = [x.iloc[-252:] for x in (score, sub, senti, price, div)]; rawa = rawa.loc[sub.index]

def label(x):  # CNN zones
    return "Extreme Fear" if x < 25 else "Fear" if x < 45 else "Neutral" if x < 55 else "Greed" if x < 75 else "Extreme Greed"
t, y = float(score.iloc[-1]), float(score.iloc[-2]); d = sub.index[-1].date()
contrib = (sub.iloc[-1] - sub.iloc[-2]) / 7; drv = contrib.abs().idxmax()

NZ = "Pacific/Auckland"
def asof_of(k):
    if k in ("momentum",): L = LIVE["^GSPC"]
    elif k in ("volatility", "putcall"): L = LIVE["^VIX"]
    elif k == "safehaven": L = LIVE["SPY"]
    else: L = None
    if L: return L["asof"].tz_convert(NZ), L["live"]
    dt = memb_asof if k in ("strength", "breadth") else junk.index[-1]
    return (pd.Timestamp(dt).tz_localize("America/New_York") + pd.Timedelta(hours=16)).tz_convert(NZ), False  # US close of that day

META = {  # name, value formatter, note
    "momentum":   ("Market Momentum", lambda v: f"{v:+.2f}%", f"S&P 500 {LIVE['^GSPC']['price']:,.0f} vs 125-day MA"),
    "strength":   ("Stock Price Strength", lambda v: f"{v:+.1f}%", "Net 52-wk highs − lows (S&P 500 members)*"),
    "breadth":    ("Stock Price Breadth", lambda v: f"{v:,.0f}", "McClellan Volume Summation (S&P 500)*"),
    "putcall":    ("Put/Call Options", lambda v: f"{v:.3f}", "5-day avg VIX / VIX3M*"),
    "volatility": ("Market Volatility", lambda v: f"{v:+.1f}%", f"VIX {LIVE['^VIX']['price']:.2f} vs 50-day MA"),
    "safehaven":  ("Safe Haven Demand", lambda v: f"{v:+.2f} pp", "20-day SPY − TLT return*"),
    "junk":       ("Junk Bond Demand", lambda v: f"{v:.2f}%", "HY − IG option-adj. spread (FRED)"),
}
comps = []
for k, (nm, fv, note) in META.items():
    a, lv = asof_of(k); v, pv = float(rawa[k].iloc[-1]), float(rawa[k].iloc[-2])
    comps.append(dict(key=k, name=nm, val=fv(v), raw=v, prev_raw=pv, chg=f"{abs(sub[k].iloc[-1] - sub[k].iloc[-2]):.0f} pts", chg_num=float(sub[k].iloc[-1] - sub[k].iloc[-2]),
                      sub=float(sub[k].iloc[-1]), sub_label=label(float(sub[k].iloc[-1])), note=note, live=lv,
                      asof_nz=a.isoformat(), asof_label=f"{'● Live' if lv else 'Close'} · {a:%a %d %b %H:%M} NZT",
                      spark=[float(x) for x in rawa[k].iloc[-60:]]))
MARKET = "Live" if LIVE["^GSPC"]["live"] else "Market closed"
names = {k: v[0] for k, v in META.items()}
expl = (f"Risk Mood {t:.0f} ({label(t)}), {'up' if t >= y else 'down'} {abs(t - y):.0f} from {y:.0f} at the prior session; "
        f"biggest mover: {names[drv]} ({sub[drv].iloc[-1]:.0f}/100, {contrib[drv]:+.1f} pts). "
        f"Weakest: {names[sub.iloc[-1].idxmin()]} ({sub.iloc[-1].min():.0f}); strongest: {names[sub.iloc[-1].idxmax()]} ({sub.iloc[-1].max():.0f}).")
if div.iloc[-1]: expl += f" Divergence: options/vol {senti.iloc[-1]:.0f} vs price/breadth {price.iloc[-1]:.0f}."
SRC = ("Yahoo Finance (^GSPC, ^VIX, ^VIX3M, SPY, TLT, S&P 500 members), FRED ICE BofA OAS. "
       "* = proxy: highs/lows & volume breadth use S&P 500 members not NYSE; put/call uses VIX/VIX3M term structure; safe haven uses TLT")
post = (f"Risk Mood (CNN-style Fear & Greed): {t:.0f}/100 {label(t)} ({t - y:+.0f})\n\n"
        + "\n".join(f"{c['name']}: {c['sub']:.0f}" for c in comps))[:280]

print("Date:", d, "| market:", MARKET)
for c in comps: print(f"  {c['name']:22s} {c['val']:>12s}  sub {c['sub']:5.1f}  {c['asof_label']}")
print(f"Score {t:.1f} (prev {y:.1f}) {label(t)}"); print("Explanation:", expl)
open("xpost.txt", "w").write(post)

plt.style.use("dark_background")
fig, ax = plt.subplots(figsize=(12, 5), facecolor="#0e1117")
for lo, hi, c in [(0, 25, "#8b1e1e"), (25, 45, "#c0583a"), (45, 55, "#666"), (55, 75, "#4f9a5a"), (75, 100, "#1f7a3a")]:
    ax.axhspan(lo, hi, color=c, alpha=.18)
ax.plot(score.index, score, color="white", lw=1.6); ax.set_ylim(0, 100); ax.grid(alpha=.15)
ax.set_title(f"Risk Mood {t:.0f} - {label(t)} ({d})", loc="left")
fig.savefig("chart.png", dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())

import dashboard
D = dict(score=t, prev=y, label=label(t), date=str(d), expl=expl, src=SRC, comps=comps, div=bool(div.iloc[-1]),
         sent=float(senti.iloc[-1]), price=float(price.iloc[-1]), trend=[float(x) for x in score.iloc[-30:]],
         trend_start=str(score.index[-30].date()), market=MARKET)
dashboard.build(D); dashboard.build_site(D)
print("Wrote site/, card.png, dashboard.html")
