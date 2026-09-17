#!/usr/bin/env python3
"""Check every URL cited in the corpus, and every fragment anchor.

A fabricated citation is worse than no citation in a document whose whole claim
is that it is authoritative, so the links are checked rather than assumed. This
is off by default in `scripts/check.sh` because it needs the network and is slow;
run it before publishing, and when adding sources.

    ARCHIFY_CHECK_URLS=1 ./scripts/check.sh
    python3 scripts/check_urls.py

Some hosts refuse automated requests outright (403 from a bot wall is not a dead
link). Those are listed in ALLOW_403 with the reason.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

LINK = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
UA = "Mozilla/5.0 (compatible; archify-link-check/1)"

# Hosts that answer a scripted HEAD/GET with a challenge rather than the page.
# A failure from one of these is not evidence the citation is wrong.
ALLOW_403 = {
    "dl.acm.org": "Cloudflare bot wall; cited bibliographically instead",
    "www.oreilly.com": "paywall challenge",
    "learning.oreilly.com": "paywall challenge",
}


def urls(root: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", ".github")]
        for name in sorted(filenames):
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            for url in LINK.findall(open(path, encoding="utf-8").read()):
                found.setdefault(url, []).append(os.path.relpath(path, root))
    return found


def check(url: str) -> tuple[str, str]:
    """Return (url, problem) — problem is "" when the link is good.

    Retries transient failures. Several of the hosts cited here rate-limit, and
    a reset connection reported as a dead link would make this check something
    people learn to ignore."""
    base, _, fragment = url.partition("#")
    req = urllib.request.Request(base, headers={"User-Agent": UA})
    body = ""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read(4_000_000).decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 403 and urllib.parse.urlparse(base).netloc in ALLOW_403:
                return url, ""
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            return url, f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            return url, f"{type(exc).__name__}: {exc}"

    if fragment and f'id="{fragment}"' not in body and f"id='{fragment}'" not in body:
        if f'name="{fragment}"' not in body:
            return url, f"fragment #{fragment} not present in the page"
    return url, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = os.path.abspath(args.root)

    found = urls(root)
    problems = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for url, problem in pool.map(check, sorted(found)):
            if problem:
                problems.append((url, problem, found[url]))

    for url, problem, where in problems:
        print(f"{problem}: {url}")
        for w in sorted(set(where)):
            print(f"    cited in {w}")

    print(f"\n{len(found)} distinct URLs checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
