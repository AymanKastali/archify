#!/usr/bin/env python3
"""Run the architecture test's own logic against known-good and known-bad edges.

`standards/modular-monolith/enforcement.md` prints a `forbidden(from, to)`
function that decides which imports are allowed to cross which boundary. That
function is the highest-stakes code in the corpus: a project copies it in, CI
goes green, and everyone believes the boundaries hold.

It is also easy to get subtly wrong in a way that passes silently. An earlier
version classified anything whose first path segment had no dot as standard
library — which is true of `myapp`, so every internal import was skipped and the
test asserted nothing while reporting `ok`.

So: extract the function from the page, compile it against a table of edges that
must be refused and edges that must be allowed, and run it. `forbidden` and
`classify` use only `strings`, so this needs no network and no module cache.

    python3 scripts/check_arch_rules.py [--root DIR]
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

PAGE = os.path.join("standards", "modular-monolith", "enforcement.md")

CTX = "myapp/internal/contexts"

# (from, to) that the rules must refuse, with the word the reason should carry.
MUST_REFUSE = [
    (f"myapp/internal/platform/outbox", f"{CTX}/ordering/published", "platform"),
    (f"{CTX}/shipping/internal/application/command", f"{CTX}/ordering/published", "adapters"),
    (f"{CTX}/shipping/internal/domain/shipment", f"{CTX}/ordering/published", "adapters"),
    (f"{CTX}/ordering/internal/domain/order", "myapp/internal/platform/clock", "domain"),
    (f"{CTX}/ordering/internal/domain/order", f"{CTX}/ordering/internal/application/command", "domain"),
    (f"{CTX}/ordering/internal/application/command", "myapp/internal/platform/clock", "port"),
    (f"{CTX}/ordering/published", f"{CTX}/ordering/internal/domain/order", "plain data"),
    (f"{CTX}/shipping/internal/adapters/inbound/acl", f"{CTX}/ordering", "published/"),
    (f"{CTX}/shipping", f"{CTX}/ordering/internal/domain/order", "published/"),
]

# (from, to) that the rules must allow. A rule that refuses these is worse than
# no rule, because it trains people to ignore the output.
MUST_ALLOW = [
    (f"{CTX}/ordering/internal/domain/order", "time"),
    (f"{CTX}/ordering/internal/domain/order", "github.com/google/uuid"),
    (f"{CTX}/ordering/internal/domain/order", f"{CTX}/ordering/internal/domain/money"),
    (f"{CTX}/ordering/internal/application/command", f"{CTX}/ordering/internal/domain/order"),
    (f"{CTX}/ordering/internal/adapters/outbound/postgres", "myapp/internal/platform/postgres"),
    (f"{CTX}/ordering/internal/adapters/outbound/postgres", f"{CTX}/ordering/internal/domain/order"),
    (f"{CTX}/ordering", f"{CTX}/ordering/internal/application/command"),
    (f"{CTX}/ordering", f"{CTX}/ordering/internal/application/query"),
    (f"{CTX}/ordering", f"{CTX}/ordering/published"),
    (f"{CTX}/shipping", f"{CTX}/ordering/published"),
    (f"{CTX}/shipping/internal/adapters/inbound/acl", f"{CTX}/ordering/published"),
    ("myapp/internal/composition", f"{CTX}/ordering"),
    ("myapp/internal/composition", f"{CTX}/shipping"),
    ("myapp/internal/composition", "myapp/internal/platform/postgres"),
    ("myapp/cmd/app", "myapp/internal/composition"),
    ("myapp/internal/platform/outbox", "myapp/internal/platform/postgres"),
]

HARNESS = '''
package arch

import "testing"

func TestMustRefuse(t *testing.T) {
	cases := []struct{ from, to, want string }{
%s
	}
	for _, c := range cases {
		got := forbidden(c.from, c.to)
		if got == "" {
			t.Errorf("forbidden(%%q, %%q) = \\"\\" — this edge must be refused", c.from, c.to)
			continue
		}
		if !contains(got, c.want) {
			t.Errorf("forbidden(%%q, %%q) = %%q, expected the reason to mention %%q", c.from, c.to, got, c.want)
		}
	}
}

func TestMustAllow(t *testing.T) {
	cases := []struct{ from, to string }{
%s
	}
	for _, c := range cases {
		if got := forbidden(c.from, c.to); got != "" {
			t.Errorf("forbidden(%%q, %%q) = %%q — this edge is legitimate", c.from, c.to, got)
		}
	}
}

func contains(haystack, needle string) bool {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return true
		}
	}
	return false
}
'''


def extract(root: str) -> str:
    """Pull `const module`, `forbidden` and `classify` out of the page."""
    text = open(os.path.join(root, PAGE), encoding="utf-8").read()
    blocks = re.findall(r"```go\n(.*?)\n```", text, re.S)
    source = next((b for b in blocks if "func forbidden(" in b), None)
    if source is None:
        raise SystemExit(f"{PAGE}: no Go block defining forbidden() — has the page moved?")

    wanted = []
    const = re.search(r'^const module = .*$', source, re.M)
    if not const:
        raise SystemExit(f"{PAGE}: forbidden() block no longer declares `const module`")
    wanted.append(const.group(0))

    for name in ("forbidden", "classify"):
        m = re.search(r"^func " + name + r"\(.*?^}", source, re.M | re.S)
        if not m:
            raise SystemExit(f"{PAGE}: could not find func {name}")
        wanted.append(m.group(0))

    return 'package arch\n\nimport "strings"\n\n' + "\n\n".join(wanted) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = os.path.abspath(args.root)

    go = shutil.which("go")
    if go is None:
        print("go not installed — skipping the architecture-rule check")
        return 0

    rules = extract(root)

    refuse = "\n".join(f'\t\t{{{f!r}, {t!r}, {w!r}}},'.replace("'", '"')
                       for f, t, w in MUST_REFUSE)
    allow = "\n".join(f'\t\t{{{f!r}, {t!r}}},'.replace("'", '"')
                      for f, t in MUST_ALLOW)

    with tempfile.TemporaryDirectory() as tmp:
        open(os.path.join(tmp, "go.mod"), "w").write("module arch\n\ngo 1.22\n")
        open(os.path.join(tmp, "arch.go"), "w").write(rules)
        open(os.path.join(tmp, "arch_test.go"), "w").write(HARNESS % (refuse, allow))
        run = subprocess.run(
            [go, "test", "-count=1", "./..."],
            cwd=tmp, capture_output=True, text=True,
            env={**os.environ, "GOFLAGS": "-mod=mod", "GOPROXY": "off"},
        )
        sys.stdout.write(run.stdout)
        sys.stderr.write(run.stderr)
        if run.returncode != 0:
            return 1

    print(f"architecture rules: {len(MUST_REFUSE)} refused, {len(MUST_ALLOW)} allowed, as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
