#!/usr/bin/env python3
import json
import re
import subprocess
import urllib.request
from collections import Counter
from pathlib import Path

AUTHOR = "aditya-786"
README = Path(__file__).resolve().parent.parent / "README.md"
CONTRIB = ("<!-- CONTRIB:START -->", "<!-- CONTRIB:END -->")
CP = ("<!-- CP:START -->", "<!-- CP:END -->")

CF_HANDLE = "Adi_7861"
CC_HANDLE = "adi_7861"

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
UA = {"User-Agent": "Mozilla/5.0 (profile-readme)"}


def gh_json(args):
    out = subprocess.run(
        ["gh"] + args, capture_output=True, text=True, check=True
    ).stdout
    return json.loads(out) if out.strip() else []


def http_get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


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


def is_approved(repo, number):
    reviews = gh_json(
        ["api", f"repos/{repo}/pulls/{number}/reviews",
         "--jq", "[.[] | {u: .user.login, s: .state}]"]
    )
    latest = {}
    for r in reviews:
        if r["s"] in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[r["u"]] = r["s"]
    states = set(latest.values())
    return "APPROVED" in states and "CHANGES_REQUESTED" not in states


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


def badge_status(repo, number, state, approved):
    if state == "open" and approved:
        return "![](https://img.shields.io/badge/approved-1f6feb?style=flat-square)"
    return (
        f"![](https://img.shields.io/github/pulls/detail/state/{repo}/{number}"
        f"?style=flat-square&label=)"
    )


def replace_block(text, markers, body):
    start, end = markers
    return re.sub(
        re.escape(start) + r".*?" + re.escape(end),
        f"{start}\n{body}\n{end}",
        text,
        flags=re.DOTALL,
    )


def cf_solved(handle):
    data = json.loads(
        http_get(f"https://codeforces.com/api/user.status?handle={handle}")
    )
    if data.get("status") != "OK":
        raise RuntimeError("codeforces api not ok")
    solved = {
        (s["problem"].get("contestId"), s["problem"].get("index"))
        for s in data["result"]
        if s.get("verdict") == "OK"
    }
    return len(solved)


def cc_solved(handle):
    html = http_get(f"https://www.codechef.com/users/{handle}")
    match = re.search(r"Total Problems Solved:\s*(\d+)", html)
    if not match:
        raise RuntimeError("codechef solved count not found")
    return int(match.group(1))


def build_contributions(text):
    repo_stars = {repo: stars(repo) for repo in REPOS}
    entries = []
    for repo, lang in REPOS.items():
        for p in prs(repo):
            approved = p["state"] == "open" and is_approved(repo, p["number"])
            entries.append(
                {
                    "repo": repo,
                    "lang": lang,
                    "stars": repo_stars[repo],
                    "number": p["number"],
                    "url": p["url"],
                    "title": clean_title(p["title"]),
                    "state": p["state"],
                    "approved": approved,
                }
            )

    per_repo = Counter(e["repo"] for e in entries)
    entries.sort(
        key=lambda e: (
            -per_repo[e["repo"]],
            -e["stars"],
            e["repo"],
            ORDER[e["state"]],
            -e["number"],
        )
    )

    merged = sum(1 for e in entries if e["state"] == "merged")
    approved = sum(1 for e in entries if e["approved"])
    open_n = sum(1 for e in entries if e["state"] == "open")
    projects = len({e["repo"] for e in entries})
    total_stars = sum(repo_stars[r] for r in {e["repo"] for e in entries})

    approved_note = f" · {approved} approved" if approved else ""
    lines = [
        f"> **{merged} merged{approved_note} · {open_n} in review** across "
        f"**{projects} open-source projects** totalling "
        f"**{fmt_stars(total_stars)}★**  ",
        "> _Every PR is self-found and ships with a fail-before / pass-after "
        "test. Status reflects live GitHub state._\n",
        "| Project | Contribution | Stars | Status |",
        "|:--|:--|:--:|:--:|",
    ]
    for e in entries:
        name = e["repo"].split("/")[-1]
        proj = f"**[{name}](https://github.com/{e['repo']})** ·&nbsp;`{e['lang']}`"
        contrib = f"[{e['title']}]({e['url']})"
        status = badge_status(e["repo"], e["number"], e["state"], e["approved"])
        lines.append(
            f"| {proj} | {contrib} | {badge_stars(e['repo'])} | {status} |"
        )

    print(f"Contributions: {len(entries)} rows "
          f"({merged} merged, {approved} approved, {open_n} open).")
    return replace_block(text, CONTRIB, "\n".join(lines))


def build_cp(text):
    try:
        cf = cf_solved(CF_HANDLE)
        cc = cc_solved(CC_HANDLE)
    except Exception as exc:
        print(f"CP stats skipped ({exc}); keeping existing values.")
        return text

    cf_badge = (
        f"![](https://img.shields.io/badge/Problems%20Solved-{cf}-1c8ac8"
        f"?style=flat-square&logo=codeforces&logoColor=white)"
    )
    cc_badge = (
        f"![](https://img.shields.io/badge/Problems%20Solved-{cc}-5B4638"
        f"?style=flat-square&logo=codechef&logoColor=white)"
    )
    body = "\n".join(
        [
            f"- **Codeforces — Candidate Master** · "
            f"[{CF_HANDLE}](https://codeforces.com/profile/{CF_HANDLE}) "
            f"&nbsp; {cf_badge}",
            f"- **CodeChef — 5★** · "
            f"[{CC_HANDLE}](https://www.codechef.com/users/{CC_HANDLE}) — "
            f"Global Rank 45, Div-1 Long Challenge &nbsp; {cc_badge}",
        ]
    )
    print(f"CP stats: Codeforces {cf} solved, CodeChef {cc} solved.")
    return replace_block(text, CP, body)


def main():
    text = README.read_text()
    text = build_contributions(text)
    text = build_cp(text)
    README.write_text(text)


if __name__ == "__main__":
    main()
