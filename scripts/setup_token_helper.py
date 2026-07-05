#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Drives `claude setup-token` non-interactively.

Spawns the CLI with piped stdio, captures the OAuth URL it prints into
logs/setup-token-url.txt, then waits (up to 5 minutes) for the authorization
code to appear in logs/setup-token-code.txt, feeds it to the CLI, and writes
the final outcome to logs/setup-token-result.txt.
"""
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

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

env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
env["BROWSER"] = "echo"  # discourage the CLI from opening a browser itself

import shutil
claude = shutil.which("claude")
if not claude:
    RESULT_FILE.write_text("FAIL: claude not on PATH", encoding="utf-8")
    sys.exit(1)

proc = subprocess.Popen(
    [claude, "setup-token"],
    cwd=str(ROOT), env=env,
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True, encoding="utf-8", errors="replace", bufsize=1,
)

buf = []
url_written = False

def reader():
    global url_written
    for line in proc.stdout:
        buf.append(line)
        RAW_FILE.write_text("".join(buf), encoding="utf-8")
        if not url_written:
            m = re.search(r"https://\S*(?:claude\.ai|anthropic\.com)\S*", line)
            if m:
                URL_FILE.write_text(m.group(0), encoding="utf-8")
                url_written = True

t = threading.Thread(target=reader, daemon=True)
t.start()

deadline = time.time() + 300
code_sent = False
while time.time() < deadline:
    if proc.poll() is not None:
        break
    if not code_sent and CODE_FILE.exists():
        code = CODE_FILE.read_text(encoding="utf-8").strip()
        if code:
            try:
                proc.stdin.write(code + "\n")
                proc.stdin.flush()
                code_sent = True
            except OSError:
                break
    time.sleep(1)

try:
    proc.wait(timeout=30)
except subprocess.TimeoutExpired:
    proc.kill()

out = "".join(buf)
ok = proc.returncode == 0 and ("Success" in out or "success" in out or "saved" in out.lower())
RESULT_FILE.write_text(("OK" if ok else f"EXIT {proc.returncode}") + "\n---\n" + out[-3000:], encoding="utf-8")
sys.exit(0 if ok else 2)
