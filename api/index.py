"""Vercel Serverless Function: Real-Time Animated LeetCode Stats SVGs (WSGI).

Endpoints:
- /card.svg   : Donut progress chart, difficulty bars, ranking & streak
- /badges.svg : Earned badges with icons & issue dates
- /streak.svg : 3-column stats card with animated green streak ring
- /           : Interactive dark-mode preview & documentation
"""

import base64
from html import escape
import io
import json
import math
import time
from urllib.parse import parse_qs

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


def landing_page(host: str, username: str) -> str:
    proto = "https"
    base = f"{proto}://{host}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Soumya Chakraborty · Real-Time LeetCode Stats API</title>
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
  <h1>⚡ Soumya's Real-Time LeetCode Stats API <span class="badge">LIVE</span></h1>
  <p>Self-hosted, real-time animated SVG stats engine deployed on Vercel. Updates in real-time on LeetCode submissions with 2-minute Edge caching.</p>

  <h3>1. Main Progress Card</h3>
  <pre>&lt;img src="{base}/card.svg" width="860" /&gt;</pre>
  <div class="card-wrap"><img src="/card.svg?user={username}" /></div>

  <h3>2. Badges Card</h3>
  <pre>&lt;img src="{base}/badges.svg" width="860" /&gt;</pre>
  <div class="card-wrap"><img src="/badges.svg?user={username}" /></div>

  <h3>3. Streak &amp; Volume Card</h3>
  <pre>&lt;img src="{base}/streak.svg" width="860" /&gt;</pre>
  <div class="card-wrap"><img src="/streak.svg?user={username}" /></div>
</body>
</html>"""


# WSGI application callable for Vercel
def app(environ, start_response):
    path = environ.get("PATH_INFO", "")
    query_str = environ.get("QUERY_STRING", "")
    qs = parse_qs(query_str)

    user = qs.get("user", qs.get("username", ["soumya-chk101"]))[0]
    static = qs.get("static", ["0"])[0] == "1"
    endpoint = qs.get("endpoint", [""])[0]

    if "card" in path or endpoint == "card":
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
        ("Cache-Control", "public, max-age=60, s-maxage=180, stale-while-revalidate=600"),
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
