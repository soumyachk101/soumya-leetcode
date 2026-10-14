"""Vercel Serverless Function: Real-Time Animated Stats SVGs (LeetCode + GitHub).

Endpoints:
- /card.svg           : LeetCode donut progress chart, difficulty bars, ranking & streak
- /badges.svg         : LeetCode earned badges with icons & issue dates
- /streak.svg         : LeetCode 3-column stats card with animated green streak ring
- /github-heatmap.svg : Real-Time GitHub 53-week contribution calendar heatmap
- /github-streak.svg  : Real-Time GitHub contributions streak card
- /highlights.svg     : Real-Time terminal highlights card with live GitHub & LeetCode numbers
- /                   : Interactive dark-mode preview & documentation
"""

import base64
from datetime import date, timedelta
from html import escape
import io
import json
import math
import re
import time
from urllib.parse import parse_qs

from bs4 import BeautifulSoup
from PIL import Image
import requests

BG = "#0d1117"
TRACK = "#161b22"
BORDER = "#30363d"
INK = "#c9d1d9"
DIM = "#8b949e"
ACCENT = "#3fb950"
LC = {"Easy": "#00b8a3", "Medium": "#ffc01e", "Hard": "#ef4743"}
FONT = "ui-monospace, SFMono-Regular, 'Cascadia Mono', Menlo, Consolas, monospace"

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"
QUERY = """
query ($user: String!) {
  allQuestionsCount { difficulty count }
  matchedUser(username: $user) {
    username
    profile { ranking }
    submitStatsGlobal { acSubmissionNum { difficulty count } }
    userCalendar { streak totalActiveDays activeYears }
    badges { name displayName icon creationDate }
  }
}
"""

DATA_CACHE = {}  # username -> (timestamp, data)
ICON_CACHE = {}  # url -> base64_png
CACHE_TTL = 120  # 2 minutes


def fetch_leetcode(username: str = "soumya-chk101") -> dict:
    now = time.time()
    if username in DATA_CACHE:
        ts, cached = DATA_CACHE[username]
        if now - ts < CACHE_TTL:
            return cached

    try:
        resp = requests.post(
            LEETCODE_GRAPHQL,
            json={"query": QUERY, "variables": {"user": username}},
            headers={
                "Content-Type": "application/json",
                "Referer": "https://leetcode.com",
                "User-Agent": "soumya-leetcode-api/1.0",
            },
            timeout=15,
        )
        resp.raise_for_status()
        res = resp.json().get("data", {})
        matched = res.get("matchedUser")
        if not matched:
            if username in DATA_CACHE:
                return DATA_CACHE[username][1]
            raise ValueError(f"User {username} not found")

        totals = {q["difficulty"]: q["count"] for q in res.get("allQuestionsCount", [])}
        solved = {
            s["difficulty"]: s["count"]
            for s in matched.get("submitStatsGlobal", {}).get("acSubmissionNum", [])
        }
        cal = matched.get("userCalendar") or {}
        badges = matched.get("badges") or []
        ranking = matched.get("profile", {}).get("ranking", 0)

        data = {
            "username": username,
            "ranking": ranking,
            "totals": totals,
            "solved": solved,
            "calendar": {
                "max_streak": cal.get("streak", 0),
                "active_days": cal.get("totalActiveDays", 0),
            },
            "badges": badges,
        }
        DATA_CACHE[username] = (now, data)
        return data
    except Exception as e:
        if username in DATA_CACHE:
            return DATA_CACHE[username][1]
        raise e


def fetch_icon_b64(url: str) -> str:
    if url in ICON_CACHE:
        return ICON_CACHE[url]
    if url.startswith("/"):
        url = "https://leetcode.com" + url
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "soumya-leetcode-api/1.0"})
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        img.thumbnail((128, 128), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()
        ICON_CACHE[url] = b64
        return b64
    except Exception:
        return ""


def render_card_svg(d: dict, static: bool = False) -> str:
    w, h = 860, 200
    cx, cy, r = 128.0, 100.0, 62.0
    stroke = 11.0
    gap_deg = 8.0
    circ = 2 * math.pi * r

    solved, totals = d.get("solved", {}), d.get("totals", {})
    ranking = d.get("ranking", 0)
    cal = d.get("calendar", {})
    streak = cal.get("max_streak", 0)
    active_days = cal.get("active_days", 0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="100%" height="100%" rx="8" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>',
    ]
    if not static:
        parts.append(
            "<style>"
            ".f{opacity:0;animation:fi .5s ease-out forwards}"
            ".b{transform:scaleX(0);transform-origin:left;animation:gr .9s ease-out forwards}"
            "@keyframes fi{to{opacity:1}}"
            "@keyframes gr{to{transform:scaleX(1)}}"
            "</style>"
        )

    def cls(name: str, delay: float) -> str:
        return "" if static else f' class="{name}" style="animation-delay:{delay:.2f}s"'

    parts.append(f'<g font-family="{FONT}">')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{TRACK}" stroke-width="{stroke}"/>')

    start_deg = -90.0
    order = ["Easy", "Medium", "Hard"]
    total_solved = max(solved.get("All", sum(solved.get(k, 0) for k in order)), 1)

    for i, name in enumerate(order):
        frac = solved.get(name, 0) / total_solved
        sweep_deg = max(frac * 360.0 - gap_deg, 2.0)
        seg = circ * sweep_deg / 360.0
        rot = start_deg + gap_deg / 2.0
        arc = (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{LC[name]}" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-dasharray="{seg:.1f} {circ - seg:.1f}" '
            f'transform="rotate({rot:.1f} {cx} {cy})"'
        )
        if static:
            parts.append(arc + "/>")
        else:
            parts.append(
                arc + f' stroke-dashoffset="{seg:.1f}">'
                f'<animate attributeName="stroke-dashoffset" from="{seg:.1f}" to="0" '
                f'begin="{0.2 + i * 0.35:.2f}s" dur="0.7s" fill="freeze"/></circle>'
            )
        start_deg += frac * 360.0

    parts.append(
        f'<g text-anchor="middle"{cls("f", 0.4)}>'
        f'<text x="{cx}" y="{cy + 2}" font-size="30" font-weight="bold" fill="{INK}">{total_solved}</text>'
        f'<text x="{cx}" y="{cy + 24}" font-size="11" fill="{DIM}">solved</text>'
        f"</g>"
    )

    bx = 268.0
    bar_w = 200.0
    count_x = bx + 60 + bar_w + 92
    y = 62.0
    for i, name in enumerate(order):
        s_count = solved.get(name, 0)
        t_count = totals.get(name, 1)
        frac = s_count / max(t_count, 1)
        parts.append(
            f'<g{cls("f", 0.3 + i * 0.15)}>'
            f'<circle cx="{bx + 5}" cy="{y - 4}" r="5" fill="{LC[name]}"/>'
            f'<text x="{bx + 18}" y="{y}" font-size="12" fill="{DIM}">{name}</text>'
            f'<text x="{count_x}" y="{y}" font-size="12" fill="{INK}" text-anchor="end">{s_count} / {t_count}</text>'
            f"</g>"
        )
        parts.append(
            f'<rect x="{bx + 78}" y="{y - 12}" width="{bar_w}" height="10" rx="5" fill="{TRACK}"/>'
            f'<rect x="{bx + 78}" y="{y - 12}" width="{max(bar_w * frac, 10):.1f}" height="10" rx="5" '
            f'fill="{LC[name]}"{cls("b", 0.35 + i * 0.15)}/>'
        )
        y += 42

    rx = count_x + 34
    parts.append(
        f'<line x1="{rx - 18}" y1="34" x2="{rx - 18}" y2="{h - 34}" stroke="{BORDER}" stroke-width="1"/>'
    )
    parts.append(
        f'<g{cls("f", 0.55)}>'
        f'<text x="{rx}" y="72" font-size="32" font-weight="bold" fill="{ACCENT}">{streak}</text>'
        f'<text x="{rx}" y="94" font-size="12" fill="{DIM}">day max streak</text>'
    )
    badge_label = "100 Days Badge"
    bw = 9 * len(badge_label) + 24
    parts.append(
        f'<rect x="{rx}" y="112" width="{bw}" height="26" rx="13" fill="none" stroke="{ACCENT}" stroke-width="1.2"/>'
        f'<text x="{rx + bw / 2}" y="{129}" font-size="12" font-weight="bold" fill="{ACCENT}" text-anchor="middle">{badge_label}</text>'
        f'<text x="{rx}" y="{166}" font-size="11" fill="{DIM}">rank #{ranking:,} &#183; {active_days} active days</text>'
        f"</g>"
    )
    parts.append(
        f'<text x="{w - 20}" y="{h - 14}" font-size="10" fill="{DIM}" text-anchor="end">leetcode.com/u/{d["username"]}</text>'
    )
    parts.append("</g></svg>")
    return "\n".join(parts)


def render_badges_svg(d: dict, static: bool = False) -> str:
    w, h = 860, 168
    icon_sz = 64

    def sort_key(b: dict) -> tuple:
        rank = {"Knight": 0, "Guardian": 0, "Annual Badge": 1, "Daily Coding Challenge": 2}
        return (rank.get(b.get("name"), 3), b.get("creationDate", ""))

    badges = sorted(d.get("badges", []), key=sort_key)
    dedup = []
    seen = set()
    for b in badges:
        disp = b.get("displayName", "")
        if disp not in seen:
            seen.add(disp)
            dedup.append(b)
    badges = dedup or badges[:5]

    slot = (w - 40) / max(len(badges), 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="100%" height="100%" rx="8" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>',
    ]
    if not static:
        parts.append(
            "<style>.f{opacity:0;animation:fi .5s ease-out forwards}@keyframes fi{to{opacity:1}}</style>"
        )

    parts.append(f'<g font-family="{FONT}" text-anchor="middle">')
    for i, b in enumerate(badges):
        cx = 20 + slot * i + slot / 2
        b64 = fetch_icon_b64(b.get("icon", ""))
        anim = "" if static else f' class="f" style="animation-delay:{0.15 + i * 0.12:.2f}s"'
        short_name = (
            b.get("displayName", "").replace(" Badge", "").replace(" LeetCoding Challenge", "")
        )
        parts.append(f"<g{anim}>")
        if b64:
            parts.append(
                f'<image x="{cx - icon_sz / 2:.0f}" y="24" width="{icon_sz}" height="{icon_sz}" '
                f'href="data:image/png;base64,{b64}"/>'
            )
        parts.append(
            f'<text x="{cx:.0f}" y="116" font-size="11" fill="{INK}">{escape(short_name)}</text>'
            f'<text x="{cx:.0f}" y="134" font-size="9.5" fill="{DIM}">{escape(b.get("creationDate", ""))}</text>'
            f"</g>"
        )

    parts.append(
        f'<text x="{w - 20}" y="{h - 14}" font-size="10" fill="{DIM}" text-anchor="end">leetcode.com/u/{d["username"]}</text>'
    )
    parts.append("</g></svg>")
    return "\n".join(parts)


def render_streak_svg(d: dict, static: bool = False) -> str:
    w, h, r = 860, 170, 46.0
    cal = d.get("calendar", {})
    active_days = cal.get("active_days", 0)
    max_streak = cal.get("max_streak", 0)
    solved = d.get("solved", {})
    solved_all = solved.get("All", 0)
    hard = solved.get("Hard", 0)
    med = solved.get("Medium", 0)

    left = (str(active_days), "total active days", "on leetcode")
    center = (str(max_streak), "day max streak", "consistent problem solving")
    right = (str(solved_all), "problems solved", f"{hard} hard &#183; {med} med")

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        f'<rect width="100%" height="100%" rx="8" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>',
    ]
    if not static:
        parts.append(
            "<style>.f{opacity:0;animation:fi .6s ease-out forwards}@keyframes fi{to{opacity:1}}</style>"
        )

    def fade(delay: float) -> str:
        return "" if static else f' class="f" style="animation-delay:{delay:.2f}s"'

    parts.append(f'<g font-family="{FONT}">')

    for cx, (val, lbl, sub), delay in (
        (150.0, left, 0.15),
        (w - 150.0, right, 0.35),
    ):
        parts.append(
            f'<g text-anchor="middle"{fade(delay)}>'
            f'<text x="{cx}" y="76" font-size="30" font-weight="bold" fill="{INK}">{val}</text>'
            f'<text x="{cx}" y="100" font-size="12" fill="{DIM}">{lbl}</text>'
            f'<text x="{cx}" y="120" font-size="11" fill="{DIM}">{sub}</text>'
            f"</g>"
        )

    for x in (300, w - 300):
        parts.append(f'<line x1="{x}" y1="30" x2="{x}" y2="{h - 30}" stroke="{BORDER}" stroke-width="1"/>')

    cx, cy = w / 2, h / 2 - 8
    circumference = 2 * math.pi * r
    ring = (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ACCENT}" '
        f'stroke-width="3" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"'
    )
    if static:
        parts.append(ring + "/>")
    else:
        parts.append(
            ring + f' stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{circumference:.1f}">'
            f'<animate attributeName="stroke-dashoffset" from="{circumference:.1f}" to="0" '
            f'begin="0.2s" dur="1.1s" fill="freeze"/></circle>'
        )

    v, l, s = center
    parts.append(
        f'<g text-anchor="middle"{fade(0.5)}>'
        f'<text x="{cx}" y="{cy + 10}" font-size="34" font-weight="bold" fill="{ACCENT}">{v}</text>'
        f'<text x="{cx}" y="{cy + r + 24}" font-size="12" fill="{DIM}">{l}</text>'
        f'<text x="{cx}" y="{cy + r + 42}" font-size="11" fill="{DIM}">{s}</text>'
        f"</g>"
    )
    parts.append("</g></svg>")
    return "\n".join(parts)


GH_PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]
GH_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
GH_CELL = 13.0
GH_GAP = 3.0
GH_STEP = GH_CELL + GH_GAP
GH_PAD = 16.0
GH_LABEL_H = 20.0
GH_FOOTER_H = 34.0
GH_DELAY = 0.015
GH_DUR = 0.4
GH_DATA_CACHE = {}  # username -> (timestamp, data)


def parse_gh_count(text: str) -> int:
    m = re.match(r"(\d+|No)\s+contribution", text.strip())
    if not m:
        return 0
    return 0 if m.group(1) == "No" else int(m.group(1))


def fetch_github_contributions(username: str = "soumyachk101") -> dict:
    now = time.time()
    if username in GH_DATA_CACHE:
        ts, cached = GH_DATA_CACHE[username]
        if now - ts < CACHE_TTL:
            return cached

    url = f"https://github.com/users/{username}/contributions"
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=15,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        cells = soup.select("td.ContributionCalendar-day[data-date]")
        if not cells:
            if username in GH_DATA_CACHE:
                return GH_DATA_CACHE[username][1]
            raise ValueError(f"No contribution cells found for {username}")

        tips = {t.get("for"): parse_gh_count(t.get_text()) for t in soup.select("tool-tip")}

        days = sorted(
            [
                {
                    "date": td["data-date"],
                    "level": int(td.get("data-level", 0)),
                    "count": tips.get(td.get("id"), 0),
                }
                for td in cells
            ],
            key=lambda d: d["date"],
        )

        total = sum(d["count"] for d in days)
        best = max(days, key=lambda d: d["count"]) if days else {"date": "", "count": 0}

        longest = run = 0
        prev = None
        for d in days:
            day = date.fromisoformat(d["date"])
            if d["count"] > 0:
                run = run + 1 if prev and day - prev == timedelta(days=1) else 1
                longest = max(longest, run)
                prev = day
            else:
                run = 0

        current = 0
        for i, d in enumerate(reversed(days)):
            if d["count"] > 0:
                current += 1
            elif i == 0:
                continue
            else:
                break

        data = {
            "username": username,
            "fetched": days[-1]["date"] if days else "",
            "total": total,
            "best_day": best,
            "longest_streak": longest,
            "current_streak": current,
            "days": days,
        }
        GH_DATA_CACHE[username] = (now, data)
        return data
    except Exception as e:
        if username in GH_DATA_CACHE:
            return GH_DATA_CACHE[username][1]
        raise


def render_github_heatmap_svg(data: dict, static: bool = False) -> str:
    days = data.get("days", [])
    if not days:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="860" height="170"><text x="20" y="50" fill="{DIM}">No GitHub data</text></svg>'

    best_date = data["best_day"]["date"]

    def dow(iso: str) -> int:
        return (date.fromisoformat(iso).weekday() + 1) % 7  # Sun=0

    weeks: list[list[dict]] = [[]]
    for d in days:
        if dow(d["date"]) == 0 and weeks[-1]:
            weeks.append([])
        weeks[-1].append(d)

    n_weeks = len(weeks)
    grid_w = n_weeks * GH_STEP - GH_GAP
    grid_h = 7 * GH_STEP - GH_GAP
    width = round(grid_w + 2 * GH_PAD)
    height = round(GH_LABEL_H + grid_h + GH_FOOTER_H + 2 * GH_PAD - 6)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" rx="8" fill="{BG}" '
        f'stroke="{BORDER}" stroke-width="1"/>',
    ]

    if not static:
        parts.append(
            "<style>"
            ".c{opacity:0;animation:pop " + f"{GH_DUR}s" + " ease-out forwards}"
            "@keyframes pop{from{opacity:0;transform:translateY(-6px)}"
            "to{opacity:1;transform:none}}"
            "</style>"
        )

    # Month labels
    parts.append(
        f'<g font-family="{FONT}" font-size="10" fill="{DIM}">'
    )
    last_label_col = -4
    prev_month = None
    for w, col in enumerate(weeks):
        m = date.fromisoformat(col[0]["date"]).month
        if m != prev_month and w - last_label_col >= 3 and w < n_weeks - 2:
            x = GH_PAD + w * GH_STEP
            parts.append(
                f'<text x="{x:.0f}" y="{GH_PAD + 9:.0f}">{GH_MONTHS[m - 1]}</text>'
            )
            last_label_col = w
        prev_month = m
    parts.append("</g>")

    # Day cells
    top = GH_PAD + GH_LABEL_H
    parts.append("<g>")
    for w, col in enumerate(weeks):
        for d in col:
            r = dow(d["date"])
            x = GH_PAD + w * GH_STEP
            y = top + r * GH_STEP
            color = (GH_PALETTE[5] if d["date"] == best_date
                     else GH_PALETTE[min(d["level"], 4)])
            attrs = ""
            if not static:
                attrs = (f' class="c" '
                         f'style="animation-delay:{(w + r) * GH_DELAY:.3f}s"')
            parts.append(
                f'<rect x="{x:.0f}" y="{y:.0f}" width="{GH_CELL:.0f}" '
                f'height="{GH_CELL:.0f}" rx="3" fill="{color}"{attrs}>'
                f'<title>{d["count"]} on {d["date"]}</title></rect>'
            )
    parts.append("</g>")

    # Footer
    fy = top + grid_h + 21
    stats = f'{data["total"]:,} contributions in the last year &#183; {data["current_streak"]} day current streak'
    parts.append(
        f'<text x="{GH_PAD:.0f}" y="{fy:.0f}" font-family="{FONT}" '
        f'font-size="11" fill="{DIM}">{stats}</text>'
    )
    legend = [f'<g font-family="{FONT}" font-size="11" fill="{DIM}">']
    lx = width - GH_PAD - 5 * (GH_CELL + 3) - 66
    legend.append(f'<text x="{lx:.0f}" y="{fy:.0f}">less</text>')
    for i in range(5):
        legend.append(
            f'<rect x="{lx + 30 + i * (GH_CELL + 3):.0f}" y="{fy - 10:.0f}" '
            f'width="{GH_CELL:.0f}" height="{GH_CELL:.0f}" rx="3" '
            f'fill="{GH_PALETTE[i]}"/>'
        )
    legend.append(
        f'<text x="{lx + 30 + 5 * (GH_CELL + 3) + 4:.0f}" y="{fy:.0f}">more</text>'
    )
    legend.append("</g>")
    parts.extend(legend)

    parts.append("</svg>")
    return "\n".join(parts)


def render_github_streak_svg(gh: dict, static: bool = False) -> str:
    left = (f"{gh['total']:,}", "total contributions", "last 12 months")
    center = (str(gh["current_streak"]), "day current streak", "daily active shipping")
    right = (str(gh["longest_streak"]), "day longest streak", f"best day {gh['best_day']['count']} commits")

    W = 860
    H = 170
    R = 46.0  # ring radius

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">',
        f'<rect width="100%" height="100%" rx="8" fill="{BG}" '
        f'stroke="{BORDER}" stroke-width="1"/>',
    ]
    if not static:
        parts.append(
            "<style>.f{opacity:0;animation:fi .6s ease-out forwards}"
            "@keyframes fi{to{opacity:1}}</style>"
        )

    def fade(delay: float) -> str:
        return "" if static else (
            f' class="f" style="animation-delay:{delay:.2f}s"'
        )

    parts.append(f'<g font-family="{FONT}">')

    # Side columns
    for cx, (value, label, sub), delay in (
        (150.0, left, 0.15),
        (W - 150.0, right, 0.35),
    ):
        parts.append(
            f'<g text-anchor="middle"{fade(delay)}>'
            f'<text x="{cx}" y="76" font-size="30" font-weight="bold" '
            f'fill="{INK}">{value}</text>'
            f'<text x="{cx}" y="100" font-size="12" fill="{DIM}">{label}</text>'
            f'<text x="{cx}" y="120" font-size="11" fill="{DIM}">{sub}</text>'
            f"</g>"
        )

    # Faint separators
    for x in (300, W - 300):
        parts.append(
            f'<line x1="{x}" y1="30" x2="{x}" y2="{H - 30}" '
            f'stroke="{BORDER}" stroke-width="1"/>'
        )

    # Center ring + stat
    cx, cy = W / 2, H / 2 - 8
    circumference = 2 * math.pi * R
    ring = (
        f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" '
        f'stroke="{ACCENT}" stroke-width="3" stroke-linecap="round" '
        f'transform="rotate(-90 {cx} {cy})"'
    )
    if static:
        parts.append(ring + "/>")
    else:
        parts.append(
            ring + f' stroke-dasharray="{circumference:.1f}" '
            f'stroke-dashoffset="{circumference:.1f}">'
            f'<animate attributeName="stroke-dashoffset" '
            f'from="{circumference:.1f}" to="0" begin="0.2s" dur="1.1s" '
            f'fill="freeze"/></circle>'
        )
    value, label, sub = center
    parts.append(
        f'<g text-anchor="middle"{fade(0.5)}>'
        f'<text x="{cx}" y="{cy + 10}" font-size="34" font-weight="bold" '
        f'fill="{ACCENT}">{value}</text>'
        f'<text x="{cx}" y="{cy + R + 24}" font-size="12" '
        f'fill="{DIM}">{label}</text>'
        f'<text x="{cx}" y="{cy + R + 42}" font-size="11" '
        f'fill="{DIM}">{sub}</text>'
        f"</g>"
    )

    parts.append("</g></svg>")
    return "\n".join(parts)


def render_highlights_svg(gh: dict, lc: dict, static: bool = False) -> str:
    gh_total = gh.get("total", 8000)
    gh_streak = gh.get("current_streak", gh.get("longest_streak", 195))

    lc_all = lc.get("solved", {}).get("All", 302)
    lc_hard = lc.get("solved", {}).get("Hard", 68)
    lc_streak = lc.get("calendar", {}).get("max_streak", 155)

    items = [
        (
            "❯",
            "#58a6ff",
            '<tspan fill="#58a6ff" font-weight="bold">Ensembyte</tspan>'
            '<tspan fill="#8b949e">: </tspan>'
            '<tspan fill="#c9d1d9">multi-agent client with </tspan>'
            '<tspan fill="#bc8cff" font-weight="600">Swift ∞ Hydra</tspan>'
            '<tspan fill="#8b949e"> &amp; </tspan>'
            '<tspan fill="#79c0ff" font-weight="600">GPUI CRDT</tspan>'
            '<tspan fill="#c9d1d9"> engine</tspan>',
        ),
        (
            "❯",
            "#58a6ff",
            '<tspan fill="#58a6ff" font-weight="bold">Orbit</tspan>'
            '<tspan fill="#8b949e">: </tspan>'
            '<tspan fill="#c9d1d9">lightweight device engine driving </tspan>'
            '<tspan fill="#f0883e" font-weight="600">Claude Code</tspan>'
            '<tspan fill="#8b949e">, </tspan>'
            '<tspan fill="#79c0ff" font-weight="600">Cursor</tspan>'
            '<tspan fill="#8b949e"> &amp; </tspan>'
            '<tspan fill="#a5d6ff" font-weight="600">Codex</tspan>',
        ),
        (
            "❯",
            "#58a6ff",
            '<tspan fill="#58a6ff" font-weight="bold">SwarmAI</tspan>'
            '<tspan fill="#8b949e">: </tspan>'
            '<tspan fill="#c9d1d9">hybrid </tspan>'
            '<tspan fill="#ffa657" font-weight="600">BM25</tspan>'
            '<tspan fill="#8b949e"> + </tspan>'
            '<tspan fill="#7ee787" font-weight="600">dense n-gram</tspan>'
            '<tspan fill="#c9d1d9"> memory for </tspan>'
            '<tspan fill="#d2a8ff" font-weight="600">parallel worktrees</tspan>',
        ),
        (
            "❯",
            "#d29922",
            '<tspan fill="#d29922" font-weight="bold">Credow</tspan>'
            '<tspan fill="#8b949e">: </tspan>'
            '<tspan fill="#c9d1d9">on-chain corporate credit on </tspan>'
            '<tspan fill="#bc8cff" font-weight="600">Algorand</tspan>'
            '<tspan fill="#8b949e"> · </tspan>'
            '<tspan fill="#ff7b72" font-weight="600">x402 vault</tspan>'
            '<tspan fill="#8b949e"> · </tspan>'
            '<tspan fill="#e3b341" font-weight="bold">FusioniX&#x27;26 Joint Winner</tspan>',
        ),
        (
            "◈",
            "#39d353",
            '<tspan fill="#8b949e">Shipped </tspan>'
            f'<tspan fill="#39d353" font-weight="bold">{gh_total:,}+</tspan>'
            '<tspan fill="#c9d1d9"> GitHub contributions with </tspan>'
            f'<tspan fill="#56d364" font-weight="bold">{gh_streak}-day</tspan>'
            '<tspan fill="#c9d1d9"> continuous streak</tspan>',
        ),
        (
            "◆",
            "#ffa116",
            '<tspan fill="#ffa116" font-weight="bold">LeetCode</tspan>'
            '<tspan fill="#8b949e"> top tier: </tspan>'
            f'<tspan fill="#e3b341" font-weight="bold">{lc_all}</tspan>'
            '<tspan fill="#c9d1d9"> solved · </tspan>'
            f'<tspan fill="#ff7b72" font-weight="bold">{lc_hard} Hard</tspan>'
            '<tspan fill="#c9d1d9"> · </tspan>'
            f'<tspan fill="#39d353" font-weight="bold">{lc_streak}-day</tspan>'
            '<tspan fill="#c9d1d9"> max streak</tspan>',
        ),
    ]

    W = 860
    TITLE = "soumyachk101@github: ~/highlights.txt"
    FS = 13.0
    LH = 30.0
    PAD_X = 24.0
    BAR_H = 34.0
    STAGGER = 0.18
    FADE = 0.45

    num_lines = len(items) + 1
    height = round(BAR_H + 16 + num_lines * LH + 14)

    def anim(i: int) -> str:
        if static:
            return ""
        begin = 0.18 + i * STAGGER
        return (
            f'<animate attributeName="opacity" from="0" to="1" '
            f'begin="{begin:.2f}s" dur="{FADE}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" '
            f'from="-8 0" to="0 0" begin="{begin:.2f}s" dur="{FADE}s" fill="freeze"/>'
        )

    op = "1" if static else "0"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" '
        f'height="{height}" viewBox="0 0 {W} {height}">',
        "<defs>",
        '  <linearGradient id="borderGrad" x1="0%" y1="0%" x2="100%" y2="100%">',
        '    <stop offset="0%" stop-color="#30363d"/>',
        '    <stop offset="50%" stop-color="#238636" stop-opacity="0.7"/>',
        '    <stop offset="100%" stop-color="#30363d"/>',
        "  </linearGradient>",
        '  <linearGradient id="barGrad" x1="0%" y1="0%" x2="100%" y2="0%">',
        '    <stop offset="0%" stop-color="#161b22"/>',
        '    <stop offset="100%" stop-color="#0d1117"/>',
        "  </linearGradient>",
        '  <radialGradient id="glow" cx="85%" cy="20%" r="50%">',
        '    <stop offset="0%" stop-color="#238636" stop-opacity="0.08"/>',
        '    <stop offset="100%" stop-color="#0d1117" stop-opacity="0"/>',
        "  </radialGradient>",
        "</defs>",
        f'<rect width="100%" height="100%" rx="9" fill="{BG}" '
        'stroke="url(#borderGrad)" stroke-width="1.2"/>',
        '<rect width="100%" height="100%" rx="9" fill="url(#glow)"/>',
        f'<path d="M1 9 a8 8 0 0 1 8-8 h{W - 18} a8 8 0 0 1 8 8 '
        f'v{BAR_H - 9} h-{W - 2} z" fill="url(#barGrad)"/>',
        f'<line x1="1" y1="{BAR_H}" x2="{W - 1}" y2="{BAR_H}" '
        f'stroke="{BORDER}" stroke-width="1"/>',
        f'<circle cx="20" cy="{BAR_H / 2}" r="5" fill="#f85149"/>',
        f'<circle cx="38" cy="{BAR_H / 2}" r="5" fill="#d29922"/>',
        f'<circle cx="56" cy="{BAR_H / 2}" r="5" fill="{ACCENT}"/>',
        f'<text x="{W / 2}" y="{BAR_H / 2 + 4.5}" fill="{DIM}" '
        f'font-family="{FONT}" font-size="12" '
        f'text-anchor="middle">{escape(TITLE)}</text>',
        '<g>',
        f'<rect x="{W - 130}" y="8" width="112" height="18" rx="9" fill="#12251a" stroke="#2ea043" stroke-width="0.8"/>',
        f'<circle cx="{W - 118}" cy="17" r="3.5" fill="#39d353">',
        '  <animate attributeName="opacity" values="1;0.3;1" dur="2s" repeatCount="indefinite"/>' if not static else "",
        '</circle>',
        f'<text x="{W - 108}" y="20.5" fill="#39d353" font-family="{FONT}" font-size="9" font-weight="bold" letter-spacing="0.5">LIVE SYNC</text>',
        '</g>',
        f'<g font-family="{FONT}" font-size="{FS}">',
    ]

    y = BAR_H + 16 + LH * 0.65
    for i, (icon, icon_color, html_content) in enumerate(items):
        parts.append(
            f'<g opacity="{op}">'
            f'<text x="{PAD_X}" y="{y:.1f}" fill="{icon_color}" '
            f'font-weight="bold">{icon}</text>'
            f'<text x="{PAD_X + 22}" y="{y:.1f}">'
            f"{html_content}</text>{anim(i)}</g>"
        )
        y += LH

    # Terminal prompt line at bottom with blinking cursor
    prompt_anim = anim(len(items))
    cursor_el = (
        '<rect x="214" y="' + f"{y - 13:.1f}" + '" width="8" height="15" fill="#39d353">'
        '<animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/>'
        '</rect>' if not static else '<rect x="214" y="' + f"{y - 13:.1f}" + '" width="8" height="15" fill="#39d353"/>'
    )
    parts.append(
        f'<g opacity="{op}">'
        f'<text x="{PAD_X}" y="{y:.1f}">'
        '<tspan fill="#3fb950" font-weight="bold">soumyachk101@github</tspan>'
        '<tspan fill="#8b949e">:</tspan>'
        '<tspan fill="#58a6ff">~</tspan>'
        '<tspan fill="#8b949e">$ </tspan>'
        f'</text>{cursor_el}{prompt_anim}</g>'
    )

    parts.append("</g></svg>")
    return "\n".join(parts)


def landing_page(host: str, username: str) -> str:
    proto = "https"
    base = f"{proto}://{host}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Soumya Chakraborty · Real-Time Stats API</title>
<style>
  body {{
    background: #0d1117;
    color: #c9d1d9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
    max-width: 900px;
    margin: 40px auto;
    padding: 0 20px;
  }}
  h1 {{ color: #58a6ff; font-family: ui-monospace, monospace; font-size: 24px; }}
  p {{ color: #8b949e; line-height: 1.6; }}
  .card-wrap {{ margin: 30px 0; }}
  img {{ max-width: 100%; height: auto; border-radius: 8px; }}
  pre {{
    background: #161b22;
    border: 1px solid #30363d;
    padding: 12px 16px;
    border-radius: 6px;
    overflow-x: auto;
    color: #7ee787;
    font-size: 13px;
  }}
  .badge {{
    display: inline-block;
    background: #238636;
    color: #fff;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: bold;
  }}
</style>
</head>
<body>
  <h1>⚡ Soumya's Real-Time Stats API <span class="badge">LIVE</span></h1>
  <p>Self-hosted, real-time animated SVG stats engine deployed on Vercel. Updates in real-time with 2-minute Edge caching.</p>

  <h3>1. LeetCode Progress Card</h3>
  <pre>&lt;img src="{base}/card.svg" width="860" /&gt;</pre>
  <div class="card-wrap"><img src="/card.svg?user={username}" /></div>

  <h3>2. LeetCode Badges Card</h3>
  <pre>&lt;img src="{base}/badges.svg" width="860" /&gt;</pre>
  <div class="card-wrap"><img src="/badges.svg?user={username}" /></div>

  <h3>3. LeetCode Streak &amp; Volume Card</h3>
  <pre>&lt;img src="{base}/streak.svg" width="860" /&gt;</pre>
  <div class="card-wrap"><img src="/streak.svg?user={username}" /></div>

  <h3>4. GitHub Contribution Heatmap (Real-Time)</h3>
  <pre>&lt;img src="{base}/github-heatmap.svg" width="860" /&gt;</pre>
  <div class="card-wrap"><img src="/github-heatmap.svg?user=soumyachk101" /></div>

  <h3>5. GitHub Streak &amp; Volume Card (Real-Time)</h3>
  <pre>&lt;img src="{base}/github-streak.svg" width="860" /&gt;</pre>
  <div class="card-wrap"><img src="/github-streak.svg?user=soumyachk101" /></div>

  <h3>6. Highlights Terminal Card (Real-Time)</h3>
  <pre>&lt;img src="{base}/highlights.svg" width="860" /&gt;</pre>
  <div class="card-wrap"><img src="/highlights.svg" /></div>
</body>
</html>"""


# WSGI application callable for Vercel
def app(environ, start_response):
    path = environ.get("PATH_INFO", "")
    query_str = environ.get("QUERY_STRING", "")
    qs = parse_qs(query_str)

    user = qs.get("user", qs.get("username", ["soumya-chk101"]))[0]
    gh_user = qs.get("gh_user", qs.get("github_user", qs.get("user", ["soumyachk101"])))[0]
    if gh_user == "soumya-chk101":
        gh_user = "soumyachk101"
    static = qs.get("static", ["0"])[0] == "1"
    endpoint = qs.get("endpoint", [""])[0]

    # Check GitHub & Highlights endpoints first to avoid 'streak' matching 'github-streak'
    if "github-heatmap" in path or endpoint == "github-heatmap":
        try:
            data = fetch_github_contributions(gh_user)
            svg = render_github_heatmap_svg(data, static=static)
            return send_svg(svg, start_response)
        except Exception as e:
            return send_error(str(e), start_response)

    elif "github-streak" in path or endpoint == "github-streak":
        try:
            data = fetch_github_contributions(gh_user)
            svg = render_github_streak_svg(data, static=static)
            return send_svg(svg, start_response)
        except Exception as e:
            return send_error(str(e), start_response)

    elif "highlight" in path or endpoint == "highlights":
        try:
            gh_data = fetch_github_contributions(gh_user)
            lc_data = fetch_leetcode(user)
            svg = render_highlights_svg(gh_data, lc_data, static=static)
            return send_svg(svg, start_response)
        except Exception as e:
            return send_error(str(e), start_response)

    elif "card" in path or endpoint == "card":
        try:
            data = fetch_leetcode(user)
            svg = render_card_svg(data, static=static)
            return send_svg(svg, start_response)
        except Exception as e:
            return send_error(str(e), start_response)

    elif "badge" in path or endpoint == "badges":
        try:
            data = fetch_leetcode(user)
            svg = render_badges_svg(data, static=static)
            return send_svg(svg, start_response)
        except Exception as e:
            return send_error(str(e), start_response)

    elif "streak" in path or endpoint == "streak":
        try:
            data = fetch_leetcode(user)
            svg = render_streak_svg(data, static=static)
            return send_svg(svg, start_response)
        except Exception as e:
            return send_error(str(e), start_response)

    else:
        host = environ.get("HTTP_HOST", "soumya-leetcode.vercel.app")
        html = landing_page(host, user).encode("utf-8")
        status = "200 OK"
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(html))),
            ("Cache-Control", "public, max-age=300"),
        ]
        start_response(status, headers)
        return [html]


def send_svg(svg_str: str, start_response):
    body = svg_str.encode("utf-8")
    status = "200 OK"
    headers = [
        ("Content-Type", "image/svg+xml; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Access-Control-Allow-Origin", "*"),
        ("Cache-Control", "public, max-age=60, s-maxage=120, stale-while-revalidate=300"),
    ]
    start_response(status, headers)
    return [body]


def send_error(msg: str, start_response):
    body = f"<svg xmlns='http://www.w3.org/2000/svg' width='500' height='100'><text x='20' y='50' fill='red'>{escape(msg)}</text></svg>".encode("utf-8")
    status = "500 Internal Server Error"
    headers = [
        ("Content-Type", "image/svg+xml; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ]
    start_response(status, headers)
    return [body]


# Also export handler for environments looking for handler
handler = app

