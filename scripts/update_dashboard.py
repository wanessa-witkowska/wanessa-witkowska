#!/usr/bin/env python3

import collections
import datetime as dt
import html
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "language-chart.svg"
COLORS = {"C#":"#A371F7", "Python":"#58A6FF", "C++":"#F778BA", "TypeScript":"#3178C6", "JavaScript":"#F1E05A", "CSS":"#C6538C", "HTML":"#E34C26", "Java":"#B07219", "Go":"#00ADD8", "Rust":"#DEA584"}
BG="#0D1117"; PANEL="#161B22"; BORDER="#30363D"; FG="#E6EDF3"; SUB="#8B949E"


def api_get(path, token):
    req = Request("https://api.github.com"+path, headers={
        "Accept":"application/vnd.github+json", "Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2022-11-28", "User-Agent":"profile-dashboard-aggregate/1.0"})
    try:
        with urlopen(req, timeout=30) as res:
            return json.load(res)
    except HTTPError as exc:
        # Avoid printing response bodies, token, or confidential metadata.
        raise RuntimeError(f"GitHub API failed with HTTP {exc.code} at an endpoint") from None
    except URLError:
        raise RuntimeError("Unable to contact GitHub API") from None


def fetch_repos(token):
    actor = api_get("/user", token)["login"]
    repos = []
    for page in range(1, 101):
        data = api_get(f"/user/repos?affiliation=owner&visibility=all&per_page=100&page={page}", token)
        if not isinstance(data, list):
            raise RuntimeError("Unexpected GitHub API result")
        # Own projects only; skip forks and archived repositories.
        repos.extend(r for r in data if r.get("owner", {}).get("login", "").casefold() == actor.casefold()
                     and not r.get("fork", False) and not r.get("archived", False))
        if len(data) < 100:
            return repos
    raise RuntimeError("Pagination limit reached; refusing to publish incomplete counts")


def render(repos, stamp):
    """Render a compact SVG card with safe spacing for every language row."""
    counts = collections.Counter((r.get("language") or "Not specified") for r in repos)
    total = len(repos)
    private = sum(bool(r.get("private")) for r in repos)
    public = total - private
    sorted_langs = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    num_languages = len(counts) - int("Not specified" in counts)

    # Dynamic height keeps footer completely outside the bar chart.
    row_h = 31
    chart_top = 231
    chart_bottom = chart_top + max(len(sorted_langs), 1) * row_h
    footer_y = chart_bottom + 36
    height = footer_y + 25

    font = 'font-family="Inter,Segoe UI,Arial,sans-serif"'
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="860" height="{height}" viewBox="0 0 860 {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Repository overview</title>',
        '<desc id="desc">Aggregate repository counts and primary languages. Private repository names, links and source code are not shown.</desc>',
        f'<rect width="860" height="{height}" rx="16" fill="{BG}"/>',
        f'<rect x="0.5" y="0.5" width="859" height="{height-1}" rx="15.5" stroke="{BORDER}" fill="none"/>',
        '<rect x="27" y="29" width="4" height="23" rx="2" fill="#58A6FF"/>',
        f'<text x="44" y="48" fill="{FG}" {font} font-size="22" font-weight="700">Repository overview</text>',
        f'<text x="832" y="46" fill="#3FB950" {font} font-size="11" text-anchor="end">● LIVE STATS</text>',
        f'<text x="28" y="73" fill="{SUB}" {font} font-size="12">Updated {html.escape(stamp)} UTC  ·  Original repositories only</text>',
    ]

    tiles = [
        ("Repositories", total, "#58A6FF"),
        ("Private", private, "#A371F7"),
        ("Public", public, "#3FB950"),
        ("Languages", num_languages, "#F0883E"),
    ]
    for i, (label, val, accent) in enumerate(tiles):
        x = 28 + i * 204
        lines.extend([
            f'<rect x="{x}" y="94" width="192" height="74" rx="10" fill="{PANEL}" stroke="{BORDER}"/>',
            f'<rect x="{x+13}" y="108" width="3" height="16" rx="1.5" fill="{accent}"/>',
            f'<text x="{x+24}" y="121" fill="{SUB}" {font} font-size="11">{label}</text>',
            f'<text x="{x+14}" y="153" fill="{FG}" {font} font-size="27" font-weight="700">{val}</text>',
        ])

    maxval = max(counts.values(), default=1)
    if not sorted_langs:
        lines.append(f'<text x="28" y="253" fill="{SUB}" {font} font-size="13">No accessible repositories</text>')
    for i, (name, value) in enumerate(sorted_langs):
        y = chart_top + i * row_h
        color = COLORS.get(name, "#6E7681")
        width = max(7, round(value / maxval * 485))
        lines.extend([
            f'<text x="28" y="{y+15}" fill="{FG}" {font} font-size="12.5">{html.escape(name)}</text>',
            f'<rect x="217" y="{y+3}" width="485" height="12" rx="6" fill="#21262D"/>',
            f'<rect x="217" y="{y+3}" width="{width}" height="12" rx="6" fill="{color}"/>',
            f'<text x="832" y="{y+15}" fill="{FG}" {font} font-size="13" font-weight="600" text-anchor="end">{value}</text>',
        ])
    lines.append('</svg>')
    return "\n".join(lines) + "\n"


def main():
    token=os.environ.get("GH_STATS_TOKEN", "")
    if not token:
        print("Missing GH_STATS_TOKEN environment variable", file=sys.stderr)
        return 1
    try:
        repos=fetch_repos(token)
    except (RuntimeError,KeyError,ValueError) as err:
        print(str(err),file=sys.stderr)
        return 1
    timestamp=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(render(repos,timestamp),encoding="utf-8")
    print(f"Generated aggregate chart for {len(repos)} owned repositories. No names logged.")
    return 0


if __name__=="__main__":
    sys.exit(main())
