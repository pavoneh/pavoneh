#!/usr/bin/env python3
"""Build a GitHub profile card using public repository data and Python's stdlib.

From the repository root:
    python3 scripts/update-profile.py
    python3 scripts/update-profile.py --input repositories.json --output assets/github-stats.svg

Offline JSON must be a list of GitHub repository objects. Each eligible repository
must include a ``languages`` object mapping GitHub language names to byte counts.
GITHUB_TOKEN is optional locally; GitHub Actions supplies its automatic token.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


USERNAME = "pavoneh"
EXCLUDED_REPOS = {"pavoneh", "guillermo1euribe"}
COLORS = ("#43e4dc", "#a78bfa", "#f0c674", "#79b8ff", "#f78cbd", "#8b949e")
API_ROOT = "https://api.github.com"


def eligible(repo):
    """Include only the user's active, public, original project repositories."""
    return (
        isinstance(repo, dict)
        and repo.get("owner", {}).get("login", "").casefold() == USERNAME.casefold()
        and repo.get("private") is False
        and repo.get("fork") is False
        and repo.get("archived") is False
        and repo.get("name", "").casefold() not in EXCLUDED_REPOS
    )


def api_json(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"{USERNAME}-profile-card",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(API_ROOT + path, headers=headers)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_repositories():
    repos = []
    page = 1
    while True:
        batch = api_json(f"/users/{USERNAME}/repos?per_page=100&type=owner&page={page}")
        if not isinstance(batch, list):
            raise ValueError("GitHub returned an unexpected repository response")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    for repo in repos:
        if eligible(repo):
            name = quote(repo["name"], safe="")
            repo["languages"] = api_json(f"/repos/{USERNAME}/{name}/languages")
    return repos


def summarize(repos):
    if not isinstance(repos, list):
        raise ValueError("Input must be a JSON list of repository objects")
    projects = [repo for repo in repos if eligible(repo)]
    language_bytes = Counter()
    stars = 0
    seen = set()
    for repo in projects:
        name = repo["name"].casefold()
        if name in seen:
            raise ValueError(f"Duplicate repository: {repo['name']}")
        seen.add(name)
        count = repo.get("stargazers_count")
        if type(count) is not int or count < 0:
            raise ValueError(f"Invalid star count for {repo['name']}")
        stars += count
        languages = repo.get("languages")
        if not isinstance(languages, dict):
            raise ValueError(f"Missing language byte counts for {repo['name']}")
        for language, count in languages.items():
            if not isinstance(language, str) or type(count) is not int or count < 0:
                raise ValueError(f"Invalid language byte counts for {repo['name']}")
            if count:
                language_bytes[language] += count
    ordered = sorted(language_bytes.items(), key=lambda item: (-item[1], item[0]))
    return {"projects": len(projects), "stars": stars, "languages": ordered}


def render_svg(stats, updated_at=None):
    updated_at = updated_at or datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        raise ValueError("Updated date must include a timezone")
    date_label = updated_at.astimezone(timezone.utc).strftime("%Y-%m-%d · UTC")
    languages = stats["languages"]
    total_bytes = sum(count for _, count in languages)
    visible = list(languages[:5])
    if len(languages) > 5:
        visible.append(("Otros", sum(count for _, count in languages[5:])))
    fragments = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="350" viewBox="0 0 1100 350" role="img" aria-labelledby="title desc">
  <title id="title">GitHub de {USERNAME}: {stats['projects']} proyectos, {stats['stars']} estrellas</title>
  <desc id="desc">Datos de repositorios públicos propios, sin forks ni archivados. Se excluyen los repositorios de perfil pavoneh y Guillermo1euribe. Lenguajes medidos por bytes de código, no por tiempo de uso. Actualizado: {date_label}.</desc>
  <defs>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#43e4dc"/><stop offset="1" stop-color="#a78bfa"/></linearGradient>
    <radialGradient id="glow"><stop stop-color="#43e4dc" stop-opacity=".08"/><stop offset="1" stop-color="#43e4dc" stop-opacity="0"/></radialGradient>
    <clipPath id="card"><rect x=".5" y=".5" width="1099" height="349" rx="20"/></clipPath>
    <clipPath id="bar"><rect x="490" y="124" width="560" height="10" rx="5"/></clipPath>
    <style>text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; }} .muted {{ fill: #8b949e; }} .label {{ fill: #c9d1d9; font-size: 14px; }} .metric {{ fill: #f0f6fc; font-size: 50px; font-weight: 700; }} .tiny {{ font-size: 12px; }}</style>
  </defs>
  <rect x=".5" y=".5" width="1099" height="349" rx="20" fill="#0d1117" stroke="#27303c"/>
  <g clip-path="url(#card)">
    <ellipse cx="130" cy="0" rx="360" ry="250" fill="url(#glow)"/>
    <rect x="35" y="0" width="160" height="3" fill="url(#accent)"/>
  </g>
  <circle cx="41" cy="43" r="4" fill="#43e4dc"/>
  <text x="54" y="48" fill="#43e4dc" font-size="13" font-weight="600" letter-spacing="2">GITHUB / SNAPSHOT</text>
  <text x="1050" y="48" text-anchor="end" class="muted tiny">{date_label}</text>
  <text x="36" y="105" fill="#f0f6fc" font-size="27" font-weight="650">Código en movimiento.</text>
  <text x="36" y="131" class="muted" font-size="14">Lo que estoy construyendo en público.</text>
  <text x="36" y="215" class="metric">{stats['projects']}</text>
  <text x="36" y="241" class="label">Proyectos públicos</text>
  <text x="252" y="215" class="metric">{stats['stars']}</text>
  <text x="252" y="241" class="label">Estrellas recibidas</text>
  <line x1="452" y1="84" x2="452" y2="267" stroke="#27303c"/>
  <text x="490" y="100" fill="#f0f6fc" font-size="17" font-weight="600">Lenguajes de código · por bytes</text>
  <rect x="490" y="124" width="560" height="10" rx="5" fill="#21262d"/>
''']
    position = 490.0
    for index, (_, count) in enumerate(visible):
        width = 560.0 * count / total_bytes
        fragments.append(f'  <rect x="{position:.3f}" y="124" width="{width:.3f}" height="10" fill="{COLORS[index]}" clip-path="url(#bar)"/>\n')
        position += width
    for index, (language, count) in enumerate(visible):
        column, row = index % 2, index // 2
        x, y = 490 + column * 290, 166 + row * 43
        percentage = count * 100 / total_bytes
        percent_label = "&lt;0.1%" if percentage < 0.1 else f"{percentage:.1f}%"
        # Keep long API language labels inside the column without omitting their name.
        name = escape(language)
        text_length = ' textLength="166" lengthAdjust="spacingAndGlyphs"' if len(language) > 20 else ""
        fragments.append(f'''  <circle cx="{x + 4}" cy="{y - 4}" r="4" fill="{COLORS[index]}"/>
  <text x="{x + 16}" y="{y}" class="label"{text_length}>{name}</text>
  <text x="{x + 270}" y="{y}" text-anchor="end" fill="{COLORS[index]}" font-size="14" font-weight="600">{percent_label}</text>
  <text x="{x + 16}" y="{y + 17}" class="muted tiny">{count:,} bytes</text>
''')
    if not visible:
        fragments.append('  <text x="490" y="175" class="muted" font-size="14">Todavía no hay datos de lenguajes disponibles.</text>\n')
    fragments.append('''  <line x1="36" y1="291" x2="1064" y2="291" stroke="#21262d"/>
  <text x="36" y="317" class="muted tiny">Fuente: GitHub API · Repositorios públicos propios · Sin forks, archivados ni repositorios de perfil</text>
  <text x="1064" y="317" text-anchor="end" fill="#a78bfa" font-size="12">@pavoneh</text>
</svg>
''')
    return "".join(fragments)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Read repository JSON instead of calling GitHub")
    parser.add_argument("--output", type=Path, default=Path("assets/github-stats.svg"))
    args = parser.parse_args()
    try:
        if args.input:
            # utf-8-sig also accepts files saved with a UTF-8 BOM on Windows.
            repos = json.loads(args.input.read_text(encoding="utf-8-sig"))
        else:
            repos = fetch_repositories()
        stats = summarize(repos)
        svg = render_svg(stats)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Write only after every request and validation succeeds.
        temporary = args.output.with_name(args.output.name + ".tmp")
        temporary.write_text(svg, encoding="utf-8", newline="\n")
        temporary.replace(args.output)
    except (HTTPError, URLError, OSError, ValueError, TypeError) as error:
        print(f"Profile update failed: {error}", file=sys.stderr)
        return 1
    print(f"Updated {args.output}: {stats['projects']} projects, {stats['stars']} stars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
