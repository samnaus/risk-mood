#!/usr/bin/env python3
"""Risk Mood prototype: blends sentiment + rates + Nasdaq + oil into a 0-100 score.
Run: .venv/bin/python riskmood.py
Sentiment: tries CNN Fear & Greed; CNN blocks bots, so falls back to VIX (inverted)."""
import json, urllib.request, pandas as pd, numpy as np, yfinance as yf
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

WIN = 252
W = {"sentiment": .30, "nasdaq": .30, "yield": .20, "oil": .20}

def cnn():
    try:
        r = urllib.request.Request("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36"})
        d = json.load(urllib.request.urlopen(r, timeout=15))["fear_and_greed_historical"]["data"]
        s = pd.Series({pd.to_datetime(p["x"], unit="ms").normalize(): p["y"] for p in d})
        return s, "CNN Fear & Greed"
    except Exception:
        return None, None

raw = yf.download(["^VIX", "^TNX", "^IXIC", "CL=F"], period="3y", progress=False, auto_adjust=False)["Close"]
raw = raw.dropna(subset=["^IXIC", "^TNX"]).ffill().dropna()
pct = lambda s: s.rolling(WIN).apply(lambda x: (x[:-1] < x[-1]).mean() * 100, raw=True)

fg, src = cnn()
sub = pd.DataFrame(index=raw.index)
if fg is not None:
    sub["sentiment"] = fg.reindex(raw.index).ffill()
else:
    src = "VIX (inverted percentile) - CNN blocked"
    sub["sentiment"] = 100 - pct(raw["^VIX"])
sub["yield"] = 100 - pct(raw["^TNX"].diff(20))       # rising yields = risk-off
sub["oil"] = 100 - pct(raw["CL=F"].pct_change(20))   # rising oil = risk-off
sub["nasdaq"] = pct(raw["^IXIC"] / raw["^IXIC"].rolling(50).mean() - 1)  # above 50d = risk-on
sub = sub.dropna()
score = sum(sub[k] * w for k, w in W.items())
price = (sub["yield"] * .2 + sub["oil"] * .2 + sub["nasdaq"] * .3) / .7
div = (sub["sentiment"] - price).abs() > 25
sub, score, raw = sub.iloc[-WIN:], score.iloc[-WIN:], raw.loc[sub.index[-WIN:]]

def label(x): return ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"][min(int(x // 20), 4)]
t, y = score.iloc[-1], score.iloc[-2]
contrib = (sub.iloc[-1] - sub.iloc[-2]) * pd.Series(W)
drv = contrib.abs().idxmax()
names = {"sentiment": "sentiment (VIX)" if fg is None else "Fear & Greed", "yield": "the 10Y yield",
         "oil": "oil", "nasdaq": "Nasdaq momentum"}
moves = {"sentiment": f"VIX {raw['^VIX'].iloc[-1]:.2f} ({raw['^VIX'].diff().iloc[-1]:+.2f})",
         "yield": f"10Y {raw['^TNX'].iloc[-1]:.2f}% ({raw['^TNX'].diff().iloc[-1]*100:+.0f}bp)",
         "oil": f"WTI ${raw['CL=F'].iloc[-1]:.2f} ({raw['CL=F'].pct_change().iloc[-1]*100:+.1f}%)",
         "nasdaq": f"Nasdaq {raw['^IXIC'].iloc[-1]:,.0f} ({raw['^IXIC'].pct_change().iloc[-1]*100:+.1f}%)"}
d = sub.index[-1].date()
expl = (f"Risk Mood {t:.0f} ({label(t)}) on {d}, {'up' if t>=y else 'down'} {abs(t-y):.0f} from {y:.0f}; "
        f"biggest driver: {names[drv]} ({moves[drv]}, {contrib[drv]:+.1f} pts).")
if div.iloc[-1]: expl += f" Divergence: sentiment {sub['sentiment'].iloc[-1]:.0f} vs prices {price.iloc[-1]:.0f}."
post = (f"Risk Mood: {t:.0f}/100 {label(t)} ({t-y:+.0f})\n\n{moves['sentiment']}\n{moves['yield']}\n"
        f"{moves['nasdaq']}\n{moves['oil']}\n\nDriver: {names[drv]}." + (" Sentiment & prices disagree." if div.iloc[-1] else ""))

print("Date:", d, "| Sentiment source:", src)
for k in W: print(f"  {k:9s} sub-score {sub[k].iloc[-1]:5.1f}  weight {W[k]:.2f}  | {moves[k]}")
print(f"Score {t:.1f} (prev {y:.1f}); price-composite {price.iloc[-1]:.1f}; divergence {bool(div.iloc[-1])}")
print("Explanation:", expl); print(f"X post ({len(post)} chars):\n{post}")
open("xpost.txt", "w").write(post)

plt.style.use("dark_background")
fig = plt.figure(figsize=(12, 8), facecolor="#0e1117")
gs = fig.add_gridspec(3, 4, height_ratios=[2.2, 1, .05], hspace=.45)
ax = fig.add_subplot(gs[0, :])
for lo, c in zip(range(0, 100, 20), ["#8b1e1e", "#c0583a", "#666666", "#4f9a5a", "#1f7a3a"]):
    ax.axhspan(lo, lo + 20, color=c, alpha=.18)
ax.plot(score.index, score, color="white", lw=1.6)
ax.scatter(score.index[div.loc[score.index]], score[div.loc[score.index]], s=8, color="#f5c542", label="divergence", zorder=3)
ax.set_ylim(0, 100); ax.set_title(f"Risk Mood  {t:.0f} - {label(t)}  ({d})", fontsize=15, loc="left")
ax.legend(loc="upper left", frameon=False); ax.grid(alpha=.15)
for i, (tk, nm) in enumerate([("^VIX", "VIX"), ("^TNX", "10Y yield %"), ("^IXIC", "Nasdaq"), ("CL=F", "WTI oil $")]):
    a = fig.add_subplot(gs[1, i]); a.plot(raw.index, raw[tk], color="#5ab4f0", lw=1)
    a.set_title(f"{nm}: {raw[tk].iloc[-1]:,.2f}", fontsize=10); a.tick_params(labelsize=7); a.grid(alpha=.15)
    a.xaxis.set_major_locator(matplotlib.dates.MonthLocator(interval=4)); a.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b"))
fig.text(.01, .01, "Data: Yahoo Finance (^VIX, ^TNX, ^IXIC, CL=F). Sentiment: " + src + ". Not financial advice.", fontsize=8, color="#999")
fig.savefig("chart.png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())

# ---- modern dashboard + share card ----
import dashboard
notes = {"sentiment": "VIX percentile, inverted", "yield": "20d change, inverted", "oil": "20d change, inverted", "nasdaq": "vs 50-day avg"}
tick = {"sentiment": "^VIX", "yield": "^TNX", "oil": "CL=F", "nasdaq": "^IXIC"}
fmt = {"sentiment": ("VIX", lambda v: f"{v:.2f}", lambda s: f"{abs(s.diff().iloc[-1]):.2f}", lambda s: s.diff().iloc[-1]),
       "yield": ("10Y Yield", lambda v: f"{v:.2f}%", lambda s: f"{abs(s.diff().iloc[-1])*100:.0f} bp", lambda s: s.diff().iloc[-1]),
       "nasdaq": ("Nasdaq", lambda v: f"{v:,.0f}", lambda s: f"{abs(s.pct_change().iloc[-1])*100:.1f}%", lambda s: s.diff().iloc[-1]),
       "oil": ("WTI Oil", lambda v: f"${v:.2f}", lambda s: f"{abs(s.pct_change().iloc[-1])*100:.1f}%", lambda s: s.diff().iloc[-1])}
comps = []
for k in ["sentiment", "yield", "nasdaq", "oil"]:
    s = raw[tick[k]]; n, fv, fc, cn = fmt[k]
    comps.append(dict(name=n, val=fv(s.iloc[-1]), chg=fc(s), chg_num=float(cn(s)), sub=float(sub[k].iloc[-1]),
                      note=notes[k], spark=[float(x) for x in s.iloc[-60:]]))
D = dict(score=float(t), prev=float(y), label=label(t), date=str(d), expl=expl, src=src, comps=comps,
                     div=bool(div.iloc[-1]), sent=float(sub["sentiment"].iloc[-1]), price=float(price.iloc[-1]),
                     trend=[float(x) for x in score.iloc[-30:]], trend_start=str(score.index[-30].date()))
dashboard.build(D)
dashboard.build_site(D)
print("Wrote dashboard.html/.png, card.html/.png")
