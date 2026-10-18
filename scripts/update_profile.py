"""Render profile cards from GitHub's API without third-party stats caches.

Uses the workflow's repository-scoped, read-only GITHUB_TOKEN. Repository
queries explicitly request public, owned, non-fork repositories. No private
repository names or contents are requested or written to generated assets.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen


QUERY = """
query Profile($login: String!, $from: DateTime!, $to: DateTime!, $after: String) {
  user(login: $login) {
    login
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar { totalContributions }
    }
    repositories(first: 100, after: $after, privacy: PUBLIC, isFork: false,
                 ownerAffiliations: [OWNER]) {
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 100) {
          pageInfo { hasNextPage }
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def graphql(token, variables):
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "github-profile-refresh"},
        method="POST",
    )
    with urlopen(request, timeout=45) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError("GitHub returned GraphQL errors; keeping existing cards")
    return payload["data"]["user"]


def count(value):
    if type(value) is not int or value < 0:
        raise ValueError("GitHub returned an invalid count")
    return value


def collect(login, token, now, fetch=graphql):
    variables = {"login": login,
                 "from": (now - timedelta(days=365)).isoformat(),
                 "to": now.isoformat(), "after": None}
    languages, colors = Counter(), {}
    repositories = stars = 0
    activity = None
    cursors = set()
    while True:
        user = fetch(token, variables.copy())
        if not user or user["login"].lower() != login.lower():
            raise RuntimeError("GitHub profile lookup failed")
        activity = activity or user["contributionsCollection"]
        connection = user["repositories"]
        for repo in connection["nodes"]:
            repositories += 1
            stars += count(repo["stargazerCount"])
            if repo["languages"]["pageInfo"]["hasNextPage"]:
                raise RuntimeError("Language data is incomplete; keeping existing cards")
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                languages[name] += count(edge["size"])
                color = edge["node"]["color"] or "#7c9fff"
                colors[name] = color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else "#7c9fff"
        page = connection["pageInfo"]
        if not page["hasNextPage"]:
            break
        cursor = page["endCursor"]
        if not cursor or cursor in cursors:
            raise RuntimeError("Invalid repository pagination")
        cursors.add(cursor)
        variables["after"] = cursor
    return {"login": login, "updated": now.strftime("%d %b %Y %H:%M UTC"),
            "commits": count(activity["totalCommitContributions"]),
            "contributions": count(activity["contributionCalendar"]["totalContributions"]),
            "prs": count(activity["totalPullRequestContributions"]),
            "stars": stars, "repositories": repositories,
            "languages": languages, "colors": colors}


def text(x, y, value, size=14, color="#c4d2e8", extra=""):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" {extra}>{escape(str(value))}</text>'


def frame(width, title, description, contents):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="244" '
            f'viewBox="0 0 {width} 244" role="img" aria-labelledby="title desc">'
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>'
            f'<rect width="{width}" height="244" rx="12" fill="#111c2e"/>'
            '<g font-family="Arial, Helvetica, sans-serif">'
            + contents + '</g></svg>\n')


def stats_svg(data):
    rows = [("Public commits", data["commits"]),
            ("Profile contributions", data["contributions"]),
            ("Pull requests", data["prs"]),
            ("Stars on public repositories", data["stars"])]
    content = text(24, 32, "GitHub activity", 21, "#55e6d2", 'font-weight="700"')
    content += text(24, 55, "Activity: past 12 months · Stars: all time", 12, "#91a6c5")
    for index, (label, value) in enumerate(rows):
        y = 89 + index * 32
        content += text(24, y, label)
        content += text(520, y, f"{value:,}", 18, "#e8f0fc", 'text-anchor="end" font-weight="700"')
    content += text(24, 228, "Updated " + data["updated"], 11, "#91a6c5")
    description = "; ".join(f"{label}: {value}" for label, value in rows)
    return frame(548, "GitHub activity for " + data["login"], description, content)


def languages_svg(data):
    content = text(24, 32, "Most used languages", 21, "#55e6d2", 'font-weight="700"')
    content += text(24, 55, "Public owned repositories · code bytes", 12, "#91a6c5")
    total = sum(data["languages"].values())
    entries = data["languages"].most_common(6)
    other = total - sum(size for _, size in entries)
    if other:
        entries.append(("Other", other))
    position = 24.0
    for name, size in entries:
        width = 340 * size / total if total else 0
        color = data["colors"].get(name, "#71829b")
        content += f'<rect x="{position:.3f}" y="72" width="{width:.3f}" height="10" fill="{color}"/>'
        position += width
    for index, (name, size) in enumerate(entries):
        x, y = 24 + (index % 2) * 174, 108 + (index // 2) * 27
        color = data["colors"].get(name, "#71829b")
        content += f'<circle cx="{x+4}" cy="{y-4}" r="4" fill="{color}"/>'
        content += text(x+14, y, f"{name} {size/total:.1%}", 11)
    if not total:
        content += text(24, 112, "No public language data yet.")
    content += text(24, 228, "Updated " + data["updated"], 11, "#91a6c5")
    description = "; ".join(f"{name}: {size/total:.1%}" for name, size in entries) if total else "No language data"
    return frame(388, "Public repository languages", description, content)


def main():
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    login = os.environ["GITHUB_USER"]
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
        raise ValueError("Invalid GitHub username")
    data = collect(login, os.environ["GITHUB_TOKEN"], now)
    # Finish both renders before replacing any existing generated cards.
    assets = {"profile-stats.svg": stats_svg(data), "top-languages.svg": languages_svg(data)}
    destination = Path(__file__).resolve().parents[1] / "assets"
    destination.mkdir(exist_ok=True)
    for name, content in assets.items():
        (destination / name).write_text(content, encoding="utf-8")
    print(f'Refreshed {login}: {data["commits"]} public commits, '
          f'{data["contributions"]} profile contributions; {data["updated"]}')


if __name__ == "__main__":
    main()
