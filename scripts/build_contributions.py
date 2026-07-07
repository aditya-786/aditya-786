#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path

AUTHOR = "aditya-786"
README = Path(__file__).resolve().parent.parent / "README.md"
START = "<!-- CONTRIB:START -->"
END = "<!-- CONTRIB:END -->"

# Curated allowlist of high-signal AI / infra projects. Add a repo here and its
# open + merged PRs by AUTHOR show up automatically on the next run.
REPOS = {
    "ollama/ollama": "Go",
    "mem0ai/mem0": "Python",
    "BerriAI/litellm": "Python",
    "khoj-ai/khoj": "Python",
    "run-llama/llama_index": "Python",
    "onyx-dot-app/onyx": "Python",
    "confident-ai/deepeval": "Python",
    "keephq/keep": "Python",
    "ogx-ai/ogx": "Python",
    "modelcontextprotocol/go-sdk": "Go",
    "modelcontextprotocol/java-sdk": "Java",
    "ray-project/kuberay": "Go",
}

ORDER = {"merged": 0, "open": 1}


def gh_json(args):
    out = subprocess.run(
        ["gh"] + args, capture_output=True, text=True, check=True
    ).stdout
    return json.loads(out) if out.strip() else []


def stars(repo):
    return gh_json(["api", f"repos/{repo}", "--jq", "{s: .stargazers_count}"])["s"]


def prs(repo):
    rows = gh_json(
        [
            "search", "prs",
            "--author", AUTHOR,
            "--repo", repo,
            "--limit", "50",
            "--json", "number,title,url,state",
        ]
    )
    return [p for p in rows if p["state"] in ORDER]


def clean_title(title):
    title = re.sub(r"^\[[^\]]*\]\s*", "", title)
    title = re.sub(r"^[a-z]+(\([^)]*\))?:\s*", "", title)
    return title[:1].upper() + title[1:]


def fmt_stars(n):
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def badge_stars(repo):
    return (
        f"![](https://img.shields.io/github/stars/{repo}"
        f"?style=flat-square&label=%E2%98%85&color=0a7e8c&labelColor=1c1c1c)"
    )


def badge_state(repo, number):
    return (
        f"![](https://img.shields.io/github/pulls/detail/state/{repo}/{number}"
        f"?style=flat-square&label=)"
    )


def main():
    repo_stars = {repo: stars(repo) for repo in REPOS}
    entries = []
    for repo, lang in REPOS.items():
        for p in prs(repo):
            entries.append(
                {
                    "repo": repo,
                    "lang": lang,
                    "stars": repo_stars[repo],
                    "number": p["number"],
                    "url": p["url"],
                    "title": clean_title(p["title"]),
                    "state": p["state"],
                }
            )

    entries.sort(key=lambda e: (ORDER[e["state"]], -e["stars"], e["repo"]))

    merged = sum(1 for e in entries if e["state"] == "merged")
    open_n = sum(1 for e in entries if e["state"] == "open")
    projects = len({e["repo"] for e in entries})
    total_stars = sum(repo_stars[r] for r in {e["repo"] for e in entries})

    lines = []
    lines.append(
        f"> **{merged} merged · {open_n} in review** across **{projects} "
        f"open-source projects** totalling **{fmt_stars(total_stars)}★**  "
    )
    lines.append(
        "> _Every PR is self-found and ships with a fail-before / pass-after "
        "test. Status badges below are live._\n"
    )
    lines.append("| Project | Contribution | Stars | Status |")
    lines.append("|:--|:--|:--:|:--:|")
    for e in entries:
        name = e["repo"].split("/")[-1]
        proj = f"**[{name}](https://github.com/{e['repo']})** ·&nbsp;`{e['lang']}`"
        contrib = f"[{e['title']}]({e['url']})"
        lines.append(
            f"| {proj} | {contrib} | {badge_stars(e['repo'])} "
            f"| {badge_state(e['repo'], e['number'])} |"
        )

    table = "\n".join(lines)
    text = README.read_text()
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        f"{START}\n{table}\n{END}",
        text,
        flags=re.DOTALL,
    )
    README.write_text(new)
    print(f"Wrote {len(entries)} rows ({merged} merged, {open_n} open).")


if __name__ == "__main__":
    main()
