#!/usr/bin/env python3
"""
Generate assets/commit-chart.svg from your GitHub contribution calendar.

Usage:
  python scripts/generate_commit_chart.py            # real data (needs GH_TOKEN)
  python scripts/generate_commit_chart.py --demo     # fake data, for previewing
  python scripts/generate_commit_chart.py --placeholder

Env:
  GH_TOKEN      GitHub token (GITHUB_TOKEN works; a PAT also counts private contributions)
  GITHUB_LOGIN  GitHub username (default: Keartipong)
"""
import json
import math
import os
import random
import sys
import urllib.request
from datetime import date, datetime

LOGIN = os.environ.get("GITHUB_LOGIN", "Keartipong")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "commit-chart.svg")

MONO = "'SF Mono','JetBrains Mono',Menlo,Consolas,'Liberation Mono',monospace"
SANS = "'Inter','Segoe UI',Helvetica,Arial,sans-serif"
PINK, AMBER, VIOLET = "#f472b6", "#fb923c", "#a78bfa"

QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount } }
      }
    }
  }
}"""


def fetch_days(login):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GH_TOKEN is not set")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-commit-chart"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        sys.exit(json.dumps(payload["errors"]))
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(datetime.strptime(d["date"], "%Y-%m-%d").date(), d["contributionCount"])
            for w in weeks for d in w["contributionDays"]]


def demo_days():
    random.seed(7)
    days, d0 = [], date.today().toordinal() - 364
    for i in range(365):
        d = date.fromordinal(d0 + i)
        base = 0 if d.weekday() >= 5 and random.random() < .6 else random.choice([0, 0, 1, 2, 3, 5, 8, 12])
        wave = 1 + .8 * math.sin(i / 38)
        days.append((d, int(base * wave)))
    return days


def streaks(days):
    longest = cur = 0
    for _, c in days:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)
    # current streak (allow today to still be empty)
    run = 0
    seq = [c for _, c in days]
    if seq and seq[-1] == 0:
        seq = seq[:-1]
    for c in reversed(seq):
        if c > 0:
            run += 1
        else:
            break
    return longest, run


def smooth_path(pts):
    """Catmull-Rom -> cubic bezier."""
    if len(pts) < 3:
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[max(i - 1, 0)]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


def card(inner, h=380):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{h}" viewBox="0 0 1000 {h}" role="img" aria-label="commit activity">
<defs>
  <linearGradient id="ln" x1="0" x2="1"><stop offset="0" stop-color="{PINK}"/><stop offset=".55" stop-color="{AMBER}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient>
  <linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PINK}" stop-opacity=".38"/><stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></linearGradient>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b0f1a"/><stop offset="1" stop-color="#141030"/></linearGradient>
  <clipPath id="rev"><rect class="reveal" x="0" y="0" width="1000" height="{h}"/></clipPath>
</defs>
<style>
  .lb{{font:500 12px {MONO};fill:#94a3b8}}
  .tt{{font:700 15px {MONO};fill:#e5e7eb}}
  .sv{{font:800 34px {SANS};fill:#f8fafc}}
  .sl{{font:500 12px {MONO};fill:#94a3b8;text-transform:uppercase;letter-spacing:1px}}
  .reveal{{transform-box:fill-box;transform-origin:0 50%;animation:rv 2.2s .2s cubic-bezier(.4,0,.2,1) both}}
  @keyframes rv{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
  .pk{{animation:pp 2.4s ease-in-out infinite}} @keyframes pp{{50%{{r:9;opacity:.5}}}}
  .fi{{animation:fi 1s 2.2s both}} @keyframes fi{{from{{opacity:0}}to{{opacity:1}}}}
</style>
<rect width="1000" height="{h}" rx="18" fill="url(#bg)"/>
<rect x=".75" y=".75" width="998.5" height="{h-1.5}" rx="17.5" fill="none" stroke="#ffffff" stroke-opacity=".12" stroke-width="1.5"/>
{inner}
</svg>'''


def build(days):
    total = sum(c for _, c in days)
    longest, current = streaks(days)
    best_day = max(days, key=lambda x: x[1])

    # weekly buckets
    weeks, cur = [], []
    for d, c in days:
        cur.append((d, c))
        if d.weekday() == 6:  # Sunday closes the week
            weeks.append(cur)
            cur = []
    if cur:
        weeks.append(cur)
    wsum = [sum(c for _, c in w) for w in weeks]
    wdate = [w[0][0] for w in weeks]

    L, R, T, B = 56, 960, 168, 328
    n = len(wsum)
    mx = max(max(wsum), 1)
    top = mx * 1.15
    xs = [L + i * (R - L) / max(n - 1, 1) for i in range(n)]
    ys = [B - (v / top) * (B - T) for v in wsum]
    pts = list(zip(xs, ys))
    line = smooth_path(pts)
    area = f"{line} L{xs[-1]:.1f},{B} L{xs[0]:.1f},{B} Z"

    grid = ""
    for k in range(4):
        gy = B - k * (B - T) / 3
        val = int(round(top * k / 3))
        grid += (f'<line x1="{L}" x2="{R}" y1="{gy:.1f}" y2="{gy:.1f}" stroke="#ffffff" stroke-opacity=".07" stroke-dasharray="3 5"/>'
                 f'<text class="lb" x="{L-10}" y="{gy+4:.1f}" text-anchor="end">{val}</text>')

    months, last_m = "", None
    for x, d in zip(xs, wdate):
        if d.month != last_m:
            last_m = d.month
            months += f'<text class="lb" x="{x:.1f}" y="{B+26}" text-anchor="middle">{d.strftime("%b").lower()}</text>'

    pi = wsum.index(max(wsum))
    px, py = pts[pi]
    anchor = "end" if px > 800 else ("start" if px < 150 else "middle")
    peak = (f'<g class="fi"><circle class="pk" cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{AMBER}"/>'
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="#fff"/>'
            f'<text class="lb" x="{px:.1f}" y="{py-16:.1f}" text-anchor="{anchor}" style="fill:#fde68a">peak week &#183; {max(wsum)}</text></g>')

    def stat(x, value, label):
        return f'<text class="sv" x="{x}" y="100">{value}</text><text class="sl" x="{x}" y="124">{label}</text>'

    stats = (stat(56, f"{total:,}", "contributions / 12 mo")
             + stat(330, f"{longest}d", "longest streak")
             + stat(560, f"{current}d", "current streak")
             + stat(790, f"{best_day[1]}", f"busiest day &#183; {best_day[0].strftime('%b %d').lower()}"))

    inner = f'''<text class="tt" x="56" y="50">// commit activity</text>
<text class="lb" x="944" y="50" text-anchor="end">@{LOGIN} &#183; weekly total</text>
{stats}
{grid}
<g clip-path="url(#rev)">
  <path d="{area}" fill="url(#ar)"/>
  <path d="{line}" fill="none" stroke="url(#ln)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
</g>
{months}
{peak}'''
    return card(inner)


def placeholder():
    inner = f'''<text class="tt" x="56" y="50">// commit activity</text>
<text class="sv" x="500" y="190" text-anchor="middle">waiting for first run</text>
<text class="lb" x="500" y="228" text-anchor="middle">Actions &#8594; "Update commit chart" &#8594; Run workflow</text>'''
    return card(inner, 300)


def main():
    if "--placeholder" in sys.argv:
        svg = placeholder()
    else:
        days = demo_days() if "--demo" in sys.argv else fetch_days(LOGIN)
        svg = build(days)
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
