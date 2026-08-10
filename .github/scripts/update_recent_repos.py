import os
import re
import sys
import urllib.request
import json

USERNAME = "tasmin-jahan"
README_PATH = "README.md"
COUNT = 4
START_MARKER = "<!--RECENT-REPOS:START-->"
END_MARKER = "<!--RECENT-REPOS:END-->"

TOKEN = os.environ.get("GITHUB_TOKEN", "")


def api_get(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_recent_repos():
    url = f"https://api.github.com/users/{USERNAME}/repos?sort=pushed&direction=desc&per_page=15"
    repos = api_get(url)
    repos = [r for r in repos if not r.get("fork")]
    return repos[:COUNT]


def build_block(repos):
    lines = ["<table>"]
    for r in repos:
        name = r["name"]
        url = r["html_url"]
        desc = r.get("description") or "No description yet."
        lang = r.get("language") or "—"
        lines.append("  <tr>")
        lines.append(f'    <td><a href="{url}"><b>{name}</b></a><br/><sub>{desc}</sub></td>')
        lines.append(f'    <td align="right"><sub>{lang}</sub></td>')
        lines.append("  </tr>")
    lines.append("</table>")
    return "\n".join(lines)


def update_readme(block):
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    replacement = f"{START_MARKER}\n{block}\n{END_MARKER}"

    if not pattern.search(content):
        print("Markers not found in README.md", file=sys.stderr)
        sys.exit(1)

    new_content = pattern.sub(replacement, content)

    if new_content == content:
        print("No changes needed.")
        return False

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("README updated.")
    return True


if __name__ == "__main__":
    repos = get_recent_repos()
    block = build_block(repos)
    update_readme(block)
