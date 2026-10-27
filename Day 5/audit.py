#!/usr/bin/env python3
"""Content auditor — standard library only.

Scans text files under --root for tokens listed in the rules file and reports
matches. Designed as a one-shot job (not a server): exit status is the contract.

Exit codes:
  0  clean run, no violations
  1  I/O or configuration error
  2  usage error (bad/missing arguments)
  3  violations found
"""
import argparse
import json
import os
import sys

EXIT_CLEAN = 0
EXIT_IO = 1
EXIT_USAGE = 2
EXIT_VIOLATIONS = 3

DEFAULT_RULES = os.environ.get("AUDIT_RULES", "/usr/local/audit/config/rules.json")


def load_rules(path):
    with open(path, encoding="utf-8") as fh:
        rules = json.load(fh)
    rules.setdefault("banned_tokens", [])
    rules.setdefault("extensions", [".txt"])
    return rules


def scan(root, rules):
    banned = rules["banned_tokens"]
    extensions = tuple(rules["extensions"])
    hits = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            if not name.endswith(extensions):
                continue
            full = os.path.join(dirpath, name)
            with open(full, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    lowered = line.lower()
                    for token in banned:
                        if token.lower() in lowered:
                            hits.append(
                                {
                                    "file": os.path.relpath(full, root),
                                    "line": lineno,
                                    "token": token,
                                }
                            )
    return hits


def render(hits, root, fmt):
    if fmt == "json":
        return json.dumps({"root": root, "violations": hits}, indent=2)
    lines = [f"root={root} violations={len(hits)}"]
    for hit in hits:
        lines.append(f"{hit['file']}:{hit['line']}: {hit['token']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="audit.py", add_help=True)
    parser.add_argument("--root", default="/usr/local/audit/sample")
    parser.add_argument("--format", default=os.environ.get("AUDIT_FORMAT", "text"),
                        choices=("text", "json"))
    parser.add_argument("--rules", default=DEFAULT_RULES)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on usage errors
        raise SystemExit(EXIT_USAGE if exc.code else EXIT_CLEAN)

    if not os.path.isdir(args.root):
        print(f"audit: root is not a directory: {args.root}", file=sys.stderr)
        return EXIT_IO

    try:
        rules = load_rules(args.rules)
    except (OSError, ValueError) as exc:
        print(f"audit: cannot load rules: {exc}", file=sys.stderr)
        return EXIT_IO

    hits = scan(args.root, rules)
    print(render(hits, args.root, args.format), flush=True)
    return EXIT_VIOLATIONS if hits else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
