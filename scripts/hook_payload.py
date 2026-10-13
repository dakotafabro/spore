#!/usr/bin/env python3
"""Read a goose hook payload on stdin and print what spore's hooks need.

Usage:
  hook_payload.py field NAME          print one top-level field, or nothing
  hook_payload.py shell-reads         print the files a shell command read

shell-reads prints one absolute path per line: files that a `cat`, `head`,
`tail`, `less`, `more` or `bat` in the command read, resolved against the
directory the command was in at that point (following any `cd` before it,
starting from the payload's working_dir), with globs expanded. Paths that
don't exist are skipped, so a relative path never counts as a file in
another directory.
"""

import glob
import json
import os
import re
import shlex
import sys

READERS = {"cat", "head", "tail", "less", "more", "bat"}
SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")"}
SESSION_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def load(stream):
    try:
        data = json.load(stream)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def field(payload, name):
    value = payload.get(name)
    if value is None:
        return ""
    value = str(value)
    if name == "session_id" and not SESSION_ID.match(value):
        return ""
    return value


def tokens(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    out = []
    try:
        for tok in lexer:
            out.append(tok)
    except ValueError:
        pass
    return out


def resolve(path, base):
    path = os.path.expanduser(path)
    return os.path.normpath(path if os.path.isabs(path) else os.path.join(base, path))


def shell_reads(command, working_dir):
    base = working_dir or os.getcwd()
    found = []
    words = []

    def flush():
        nonlocal base
        if not words:
            return
        name = os.path.basename(words[0])
        if name == "cd" and len(words) > 1:
            target = resolve(words[1], base)
            if os.path.isdir(target):
                base = target
        elif name in READERS:
            for arg in words[1:]:
                if arg.startswith("-") or arg.startswith(">") or arg.startswith("<"):
                    continue
                candidate = resolve(arg, base)
                matches = sorted(glob.glob(candidate)) if glob.has_magic(candidate) else [candidate]
                for m in matches:
                    if os.path.isfile(m) and m not in found:
                        found.append(m)
        words.clear()

    for tok in tokens(command):
        if tok in SEPARATORS or set(tok) <= set(";&|()"):
            flush()
        else:
            words.append(tok)
    flush()
    return found


def main(argv):
    payload = load(sys.stdin)
    if len(argv) == 3 and argv[1] == "field":
        print(field(payload, argv[2]))
        return 0
    if len(argv) == 2 and argv[1] == "shell-reads":
        command = field(payload, "matcher_context")
        for path in shell_reads(command, field(payload, "working_dir")):
            print(path)
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
