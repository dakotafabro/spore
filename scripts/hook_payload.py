#!/usr/bin/env python3
"""Read a goose hook payload on stdin and print what spore's hooks need.

Usage:
  hook_payload.py field NAME          print one top-level field, or nothing
  hook_payload.py shell-reads         print the files a shell command read

shell-reads prints one absolute path per line: files that a `cat`, `head`,
`tail`, `less`, `more` or `bat` in the command read, plus the file operands of
`sed`, `awk`, `grep` and `rg` (their first operand is the script or pattern
unless -e or -f supplied it, and `sed -i` is an edit, not a read), resolved
against the
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
PATTERN_READERS = {
    "sed": {"script": {"-e", "-f", "--expression", "--file"}, "value": set()},
    "awk": {"script": {"-f"}, "value": {"-v", "-F"}},
    "grep": {"script": {"-e", "-f", "--regexp", "--file"}, "value": {"-m", "-A", "-B", "-C", "--max-count", "--context"}},
    "rg": {"script": {"-e", "-f", "--regexp", "--file"}, "value": {"-m", "-A", "-B", "-C", "-g", "-t", "-T", "--glob", "--type", "--max-count", "--context"}},
}
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


def pattern_reader_files(name, args):
    spec = PATTERN_READERS[name]
    operands = []
    script_given = False
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg.startswith((">", "<")):
            continue
        if arg.startswith("-") and arg != "-":
            flag = arg.split("=", 1)[0]
            if name == "sed" and (flag == "-i" or flag.startswith("-i") or flag == "--in-place"):
                return []
            if flag in spec["script"]:
                script_given = True
                skip_next = "=" not in arg
            elif flag in spec["value"]:
                skip_next = "=" not in arg
            continue
        operands.append(arg)
    return operands if script_given else operands[1:]


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
            add([a for a in words[1:] if not a.startswith(("-", ">", "<"))])
        elif name in PATTERN_READERS:
            add(pattern_reader_files(name, words[1:]))
        words.clear()

    def add(args):
        for arg in args:
            candidate = resolve(arg, base)
            matches = sorted(glob.glob(candidate)) if glob.has_magic(candidate) else [candidate]
            for m in matches:
                if os.path.isfile(m) and m not in found:
                    found.append(m)

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
