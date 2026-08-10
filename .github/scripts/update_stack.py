import os
import re
import sys
import json
import base64
import urllib.request
import urllib.parse

USERNAME = "tasmin-jahan"
README_PATH = "README.md"
START_MARKER = "<!--STACK:START-->"
END_MARKER = "<!--STACK:END-->"
TOP_N = 10

TOKEN = os.environ.get("GITHUB_TOKEN", "")

SKILL_ICON_SLUGS = {
    "Python": "py",
    "C++": "cpp",
    "C": "c",
    "Java": "java",
    "Kotlin": "kotlin",
    "Rust": "rust",
    "JavaScript": "js",
    "TypeScript": "ts",
    "HTML": "html",
    "CSS": "css",
    "Shell": "bash",
    "Dockerfile": "docker",
    "Go": "go",
    "C#": "cs",
    "Swift": "swift",
    "PHP": "php",
    "Ruby": "ruby",
    "Vue": "vue",
    "CMake": "cmake",
    "R": "r",
    "Lua": "lua",
    "Scala": "scala",
    "Dart": "dart",
    "Haskell": "haskell",
}

# Jupyter Notebook byte counts from GitHub's languages API include the
# entire .ipynb JSON file - cell outputs, embedded images, metadata -
# not just the code. recover_python_from_notebooks() parses each
# notebook directly and counts only source bytes from code cells,
# crediting that to Python instead. Jupyter Notebook is then dropped
# from totals since its bytes have been properly reattributed.


def api_get(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_all_repos():
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}"
        batch = api_get(url)
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return [r for r in repos if not r.get("fork")]


def aggregate_languages(repos):
    totals = {}
    for r in repos:
        url = r["languages_url"]
        try:
            langs = api_get(url)
        except Exception:
            continue
        for lang, byte_count in langs.items():
            totals[lang] = totals.get(lang, 0) + byte_count
    return totals


def get_repo_tree(owner, repo, default_branch):
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    try:
        return api_get(url)
    except Exception:
        return None


def get_file_content(owner, repo, path):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{urllib.parse.quote(path)}"
    try:
        data = api_get(url)
    except Exception:
        return None
    if data.get("encoding") != "base64":
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return None


def extract_notebook_code_bytes(notebook_text):
    try:
        nb = json.loads(notebook_text)
    except Exception:
        return 0
    total = 0
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        total += len(source.encode("utf-8"))
    return total


def recover_python_from_notebooks(repos, totals):
    recovered_total = 0
    for r in repos:
        owner = r["owner"]["login"]
        repo = r["name"]
        branch = r.get("default_branch", "main")
        tree = get_repo_tree(owner, repo, branch)
        if not tree or "tree" not in tree:
            continue
        notebook_paths = [
            item["path"] for item in tree["tree"]
            if item.get("type") == "blob" and item["path"].endswith(".ipynb")
        ]
        for path in notebook_paths:
            content = get_file_content(owner, repo, path)
            if content is None:
                continue
            recovered_total += extract_notebook_code_bytes(content)

    if recovered_total > 0:
        totals["Python"] = totals.get("Python", 0) + recovered_total
    totals.pop("Jupyter Notebook", None)
    return totals


def build_block(totals):
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    ranked = [(lang, count) for lang, count in ranked if count > 0]

    slugs = []
    for lang, _ in ranked:
        slug = SKILL_ICON_SLUGS.get(lang)
        if slug and slug not in slugs:
            slugs.append(slug)
        if len(slugs) >= TOP_N:
            break

    if not slugs:
        return "<sub>Stack detection unavailable.</sub>"

    icon_list = ",".join(slugs)
    return (
        '<p align="left">\n'
        f'  <img src="https://skillicons.dev/icons?i={icon_list}" alt="stack" />\n'
        "</p>"
    )


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
    repos = get_all_repos()
    totals = aggregate_languages(repos)
    totals = recover_python_from_notebooks(repos, totals)
    block = build_block(totals)
    update_readme(block)
