#!/usr/bin/env python3
"""Structural checks over the archify corpus.

Standard library only, so this runs anywhere python3 does. Every check here
exists because the thing it checks was once wrong.

    python3 scripts/check_docs.py [--root DIR]

Exits non-zero, and prints one line per failure, if anything is wrong.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
FENCE = re.compile(r"^```(\S*)\s*$")

failures: list[str] = []
illustrative: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def markdown_files(root: str) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", ".github")]
        for name in filenames:
            if name.endswith(".md"):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def code_blocks(path: str):
    """Yield (lang, start_line, [lines]) for every fenced block in a file."""
    lines = open(path, encoding="utf-8").read().split("\n")
    lang = None
    start = 0
    buf: list[str] = []
    for i, line in enumerate(lines, 1):
        m = FENCE.match(line)
        if m and lang is None:
            lang, start, buf = m.group(1), i, []
            continue
        if line.startswith("```") and lang is not None:
            yield lang, start, buf
            lang = None
            continue
        if lang is not None:
            buf.append(line)


def check_links(files: list[str]) -> None:
    for path in files:
        text = open(path, encoding="utf-8").read()
        for _, target in LINK.findall(text):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            rel = target.split("#")[0]
            if not rel:
                continue
            full = os.path.normpath(os.path.join(os.path.dirname(path), rel))
            if not os.path.exists(full):
                fail(f"{path}: broken relative link -> {target}")


def check_fences(files: list[str]) -> None:
    for path in files:
        for lang, start, _ in code_blocks(path):
            if lang == "":
                fail(f"{path}:{start}: code fence has no language tag")
            elif lang == "md":
                fail(f"{path}:{start}: use ```markdown, not ```md")


def check_whitespace(files: list[str]) -> None:
    for path in files:
        raw = open(path, "rb").read()
        if raw and not raw.endswith(b"\n"):
            fail(f"{path}: no final newline")
        if b"\r" in raw:
            fail(f"{path}: carriage returns")
        text = raw.decode("utf-8")
        for i, line in enumerate(text.split("\n"), 1):
            if line != line.rstrip():
                fail(f"{path}:{i}: trailing whitespace")


def check_sources(root: str, files: list[str]) -> None:
    for path in files:
        rel = os.path.relpath(path, root)
        if not rel.startswith("standards" + os.sep):
            continue
        text = open(path, encoding="utf-8").read()
        n = len(re.findall(r"^## Sources\s*$", text, re.M))
        if n != 1:
            fail(f"{path}: expected exactly one '## Sources' section, found {n}")


def check_go_blocks(files: list[str]) -> None:
    """Go samples are the product. They must be indented and formatted as gofmt
    would, so that code copied out of this corpus is conformant on arrival.

    Not every block is real Go: some deliberately elide with `...`, show several
    packages at once, or put a bare call at top level to make a point about a
    call site. Those cannot be gofmt-compared, so they are counted and listed
    rather than failed — but the tab rule still applies to every one of them."""
    gofmt = shutil.which("gofmt")
    for path in files:
        for lang, start, body in code_blocks(path):
            if lang != "go":
                continue
            for offset, line in enumerate(body):
                if line.startswith(" ") and line.strip():
                    fail(f"{path}:{start + offset + 1}: Go block indented with "
                         f"spaces; gofmt uses tabs")
                    break
            if gofmt is None:
                continue
            code = "\n".join(body).strip("\n")
            if not code:
                continue
            got = _gofmt(gofmt, code)
            if got is None:
                illustrative.append(f"{path}:{start}")
            elif got != code:
                fail(f"{path}:{start}: Go block is not gofmt-formatted")


def _gofmt(gofmt: str, code: str) -> str | None:
    """Return the gofmt-formatted form of a snippet, or None if it will not
    parse. Tries it as a whole file, then as a file body."""
    file_prefix = "package p\n\n"
    body_prefix = "package p\n\nfunc _() {\n"
    for src, strip, dedent in (
        (code, "", False),
        (file_prefix + code, file_prefix, False),
        (body_prefix + _indent(code) + "\n}", body_prefix, True),
    ):
        with tempfile.NamedTemporaryFile("w", suffix=".go", delete=False) as fh:
            fh.write(src + "\n")
            tmp = fh.name
        try:
            run = subprocess.run([gofmt, "-e", tmp], capture_output=True, text=True)
        finally:
            os.unlink(tmp)
        if run.returncode == 0:
            out = run.stdout
            if strip:
                if not out.startswith(strip):
                    return None
                out = out[len(strip):]
            if dedent:
                out = out.rstrip("\n")
                if out.endswith("}"):
                    out = out[: -1].rstrip("\n")
                out = "\n".join(
                    line[1:] if line.startswith("\t") else line
                    for line in out.split("\n")
                )
            return out.strip("\n")
    return None


def _indent(code: str) -> str:
    return "\n".join("\t" + line if line.strip() else line for line in code.split("\n"))


def check_yaml_blocks(files: list[str]) -> None:
    """The .golangci.yml sample must at least be well-formed. yaml is not in the
    standard library, so this is a shallow structural check when PyYAML is
    absent: indentation consistency and no tabs."""
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None
    for path in files:
        for lang, start, body in code_blocks(path):
            if lang != "yaml":
                continue
            if any("\t" in x for x in body):
                fail(f"{path}:{start}: tab in a YAML block")
            if yaml is None:
                continue
            try:
                yaml.safe_load("\n".join(body))
            except Exception as exc:  # noqa: BLE001
                fail(f"{path}:{start}: YAML does not parse: {exc}")


def check_manifests(root: str) -> None:
    plugin_path = os.path.join(root, ".claude-plugin", "plugin.json")
    market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
    try:
        plugin = json.load(open(plugin_path, encoding="utf-8"))
        market = json.load(open(market_path, encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        fail(f"manifest does not parse: {exc}")
        return

    versions = {plugin.get("version")}
    versions |= {p.get("version") for p in market.get("plugins", [])}
    versions.add(market.get("metadata", {}).get("version"))
    if len(versions) != 1:
        fail(f"manifest versions disagree: {sorted(v or '<unset>' for v in versions)}")

    listed = sorted(s.rsplit("/", 1)[-1] for s in plugin.get("skills", []))
    on_disk = sorted(
        d for d in os.listdir(os.path.join(root, "skills"))
        if os.path.isdir(os.path.join(root, "skills", d))
    )
    if listed != on_disk:
        fail(f"plugin.json skills {listed} != skills/ on disk {on_disk}")

    for name in on_disk:
        skill = os.path.join(root, "skills", name, "SKILL.md")
        if not os.path.exists(skill):
            fail(f"skills/{name}/ has no SKILL.md")
            continue
        head = open(skill, encoding="utf-8").read().split("---")[1]
        declared = re.search(r"^name:\s*(\S+)", head, re.M)
        if not declared or declared.group(1) != name:
            fail(f"skills/{name}/SKILL.md frontmatter name != directory name")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = os.path.abspath(args.root)

    files = markdown_files(root)
    if not files:
        print("no markdown found — wrong --root?", file=sys.stderr)
        return 2

    check_links(files)
    check_fences(files)
    check_whitespace(files)
    check_sources(root, files)
    check_go_blocks(files)
    check_yaml_blocks(files)
    check_manifests(root)

    for line in failures:
        print(line)
    if illustrative and os.environ.get("ARCHIFY_VERBOSE"):
        print("\nIllustrative Go snippets, not gofmt-checkable:")
        for line in illustrative:
            print(f"  {line}")
    print(f"\n{len(files)} markdown files checked, {len(failures)} problems, "
          f"{len(illustrative)} illustrative snippets")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
