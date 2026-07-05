#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Drives `claude setup-token` through a real ConPTY (pywinpty).

Captures the OAuth URL into logs/setup-token-url.txt, then waits up to
5 minutes for logs/setup-token-code.txt to appear, types the code into the
CLI, and writes the outcome to logs/setup-token-result.txt. The raw ANSI
stream goes to logs/setup-token-raw.txt (never printed to chat)."""
import os
import re
import shutil
import sys
import time
from pathlib import Path

import winpty

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
URL_FILE = LOGS / "setup-token-url.txt"
CODE_FILE = LOGS / "setup-token-code.txt"
RESULT_FILE = LOGS / "setup-token-result.txt"
RAW_FILE = LOGS / "setup-token-raw.txt"

for f in (URL_FILE, CODE_FILE, RESULT_FILE, RAW_FILE):
    try:
        f.unlink()
    except FileNotFoundError:
        pass

claude = shutil.which("claude")
if not claude:
    RESULT_FILE.write_text("FAIL: claude not on PATH", encoding="utf-8")
    sys.exit(1)

env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[=>]")

proc = winpty.PtyProcess.spawn(
    [claude, "setup-token"], cwd=str(ROOT), env=env, dimensions=(50, 1000)
)

raw = []
clean_all = ""
url_written = False
code_sent = False
deadline = time.time() + 330
success = False

while time.time() < deadline:
    if not proc.isalive():
        break
    try:
        chunk = proc.read(4096)
    except (EOFError, OSError):
        break
    if chunk:
        raw.append(chunk)
        with open(RAW_FILE, "a", encoding="utf-8", errors="replace") as f:
            f.write(chunk)
        clean_all = ANSI.sub("", "".join(raw)).replace("\r", "")
        if not url_written:
            m = re.search(r"https://[^\s│]*(?:claude\.ai|anthropic\.com)[^\s│]*", clean_all)
            if m:
                URL_FILE.write_text(m.group(0), encoding="utf-8")
                url_written = True
        if re.search(r"sk-ant-oat|[Ss]uccess|saved|logged in", clean_all):
            success = True
            # keep reading briefly to let it finish, then exit loop
            time.sleep(2)
            break
    else:
        time.sleep(0.3)
    if url_written and not code_sent and CODE_FILE.exists():
        code = CODE_FILE.read_text(encoding="utf-8").strip()
        if code:
            proc.write(code + "\r")
            code_sent = True

try:
    if proc.isalive():
        time.sleep(3)
except Exception:
    pass

status = "OK" if success else ("TIMEOUT" if time.time() >= deadline else "EXITED")
RESULT_FILE.write_text(status + "\n", encoding="utf-8")
try:
    if proc.isalive():
        proc.terminate()
except Exception:
    pass
sys.exit(0 if success else 2)
