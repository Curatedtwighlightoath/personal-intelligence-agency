"""
GitHub API adapter for releases, commits, and repo activity.

source_config schema:
{
    "owner": "anthropics",
    "repo": "claude-code",       # required for 'releases' and 'commits'
    "watch_type": "releases",    # 'releases' or 'commits'
    "max_items": 10,             # optional, default 10
    "github_token": null         # optional — set for private repos or higher rate limits
}

Rate limits:
  - Unauthenticated: 60 requests/hour (shared by IP)
  - Authenticated: 5,000 requests/hour
  Set GITHUB_TOKEN env var or pass github_token in source_config.
"""

import hashlib
import os
from datetime import datetime, timezone

import httpx

from models import RawItem
from adapters import register_adapter

# ── Constants ────────────────────────────────────────────────────────────────

GITHUB_API = "https://api.github.com"
ACCEPT_HEADER = "application/vnd.github+json"
API_VERSION = "2022-11-28"


# ── Main Adapter ─────────────────────────────────────────────────────────────

@register_adapter("github_api")
async def fetch_github(source_config: dict) -> list[RawItem]:
    """Fetch from GitHub API, return normalized items."""
    watch_type = source_config.get("watch_type", "releases")
    owner = source_config.get("owner")
    repo = source_config.get("repo")

    if not owner:
        raise ValueError("source_config missing required field: owner")
    if not repo:
        raise ValueError("source_config missing required field: repo")

    dispatchers = {
        "releases": _fetch_releases,
        "commits": _fetch_commits,
    }

    if watch_type not in dispatchers:
        raise ValueError(
            f"Unknown watch_type '{watch_type}'. Available: {list(dispatchers.keys())}"
        )

    return await dispatchers[watch_type](source_config, owner, repo)


# ── Release Fetcher ──────────────────────────────────────────────────────────

async def _fetch_releases(config: dict, owner: str, repo: str) -> list[RawItem]:
    """Fetch releases from a GitHub repo."""
    max_items = config.get("max_items", 10)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases"

    data = await _api_get(url, config, params={"per_page": max_items})

    items = []
    for release in data:
        tag = release.get("tag_name", "unknown")
        name = release.get("name") or tag
        body = release.get("body") or "No release notes provided."
        html_url = release.get("html_url", "")
        published = release.get("published_at") or release.get("created_at")
        is_prerelease = release.get("prerelease", False)
        is_draft = release.get("draft", False)

        # Skip drafts — they're not public yet
        if is_draft:
            continue

        title = f"{owner}/{repo} {tag}"
        if is_prerelease:
            title += " (pre-release)"

        items.append(
            RawItem(
                source_url=html_url,
                title=title,
                content=_clean_markdown(body),
                published_at=published,
                item_hash=_hash_release(owner, repo, tag),
                raw_data={
                    "owner": owner,
                    "repo": repo,
                    "tag": tag,
                    "name": name,
                    "prerelease": is_prerelease,
                    "author": release.get("author", {}).get("login"),
                    "assets_count": len(release.get("assets", [])),
                },
            )
        )

    return items


# ── Commit Fetcher ───────────────────────────────────────────────────────────

async def _fetch_commits(config: dict, owner: str, repo: str) -> list[RawItem]:
    """Fetch recent commits from a GitHub repo."""
    max_items = config.get("max_items", 10)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"

    data = await _api_get(url, config, params={"per_page": max_items})

    items = []
    for commit_data in data:
        sha = commit_data.get("sha", "")[:8]
        commit = commit_data.get("commit", {})
        message = commit.get("message", "No commit message")
        html_url = commit_data.get("html_url", "")
        author_info = commit.get("author", {})
        committer = (commit_data.get("author") or {}).get("login") or author_info.get("name", "unknown")
        date = author_info.get("date")

        # Use first line of commit message as title
        first_line = message.split("\n")[0][:120]
        full_message = message

        items.append(
            RawItem(
                source_url=html_url,
                title=f"{owner}/{repo}@{sha}: {first_line}",
                content=full_message,
                published_at=date,
                item_hash=_hash_commit(owner, repo, commit_data.get("sha", "")),
                raw_data={
                    "owner": owner,
                    "repo": repo,
                    "sha": commit_data.get("sha", ""),
                    "author": committer,
                    "files_changed": commit_data.get("stats", {}).get("total", None),
                },
            )
        )

    return items


# ── HTTP Layer ───────────────────────────────────────────────────────────────

async def _api_get(url: str, config: dict, params: dict = None) -> list[dict]:
    """Make an authenticated GET request to the GitHub API."""
    token = config.get("github_token") or os.environ.get("GITHUB_TOKEN")

    headers = {
        "Accept": ACCEPT_HEADER,
        "X-GitHub-Api-Version": API_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, params=params, follow_redirects=True)
        response.raise_for_status()

    data = response.json()

    # API should return a list; if it's a dict, something unexpected happened
    if isinstance(data, dict):
        message = data.get("message", "Unknown error")
        raise ValueError(f"GitHub API error: {message}")

    return data


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clean_markdown(text: str) -> str:
    """Light cleanup of GitHub release notes markdown.
    We keep it mostly intact since the LLM can handle markdown —
    just trim excessive whitespace and truncate if huge."""
    if not text:
        return ""
    # Collapse multiple blank lines
    import re
    clean = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Truncate very long release notes (some repos dump full changelogs)
    if len(clean) > 2000:
        clean = clean[:2000] + "\n\n[truncated]"
    return clean


def _hash_release(owner: str, repo: str, tag: str) -> str:
    """Dedup hash for a release."""
    content = f"github|{owner}/{repo}|release|{tag}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _hash_commit(owner: str, repo: str, sha: str) -> str:
    """Dedup hash for a commit."""
    content = f"github|{owner}/{repo}|commit|{sha}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]