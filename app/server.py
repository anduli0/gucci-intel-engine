#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gucci Intelligence desktop app — local server (stdlib only).

Serves the dashboard UI and JSON APIs over 127.0.0.1, and can launch the
report pipelines headlessly via `claude -p "/daily-gucci"` etc.

    python app/server.py [--port 8790] [--root <project root>]
"""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parent
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALLOWED_CMDS = {"daily-gucci", "daily-brief", "weekly-luxury", "event-response", "news-scrap", "gucci-special", "gucci-products"}
REPORT_CATEGORIES = ("special", "cd", "daily", "weekly", "events")

RUN_LOCK = threading.Lock()
RUN_STATE = {"proc": None, "cmd": None, "arg": "", "started": None, "log": None, "exit": None}


def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


SUBPATH = "/gucci"  # public Tailscale funnel path; the proxy does not strip it


class Handler(BaseHTTPRequestHandler):
    server_version = "GucciIntel/1.0"

    @property
    def root(self):
        return self.server.project_root

    @property
    def readonly(self):
        return getattr(self.server, "readonly", False)

    def _strip_subpath(self, route):
        """Serve both at / (local) and under /gucci (public funnel)."""
        if route == SUBPATH:
            return None  # caller must redirect to SUBPATH + "/"
        if route.startswith(SUBPATH + "/"):
            return route[len(SUBPATH):]
        return route

    def log_message(self, fmt, *args):  # quiet console
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # CORS: lets the always-on GitHub Pages viewer drive this engine remotely
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Run-Key")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Run-Key")
        self.end_headers()

    def _run_key(self):
        p = self.root / "data" / "run-key.txt"
        try:
            return p.read_text(encoding="utf-8").strip()
        except OSError:
            return None

    def _key_ok(self):
        key = self._run_key()
        return bool(key) and self.headers.get("X-Run-Key", "") == key

    def _lock_path(self):
        return self.root / "logs" / "run.lock"

    def _lock_read(self):
        """Cross-process run lock (two server instances share the pipelines)."""
        p = self._lock_path()
        try:
            info = json.loads(p.read_text(encoding="utf-8"))
            started = datetime.strptime(info["started"], "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - started).total_seconds() < 3 * 3600:
                return info
            p.unlink()  # stale
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
        return None

    def _json(self, obj, code=200):
        self._send(code, json_bytes(obj))

    # ---------- GET ----------

    def do_GET(self):
        parsed = urlparse(self.path)
        route = self._strip_subpath(parsed.path)
        if route is None:  # /gucci without trailing slash: relative URLs need it
            self.send_response(301)
            self.send_header("Location", SUBPATH + "/")
            self.end_headers()
            return
        qs = parse_qs(parsed.query)
        try:
            if route in ("/", "/index.html"):
                page = (APP_DIR / "ui" / "index.html").read_bytes()
                self._send(200, page, "text/html; charset=utf-8")
            elif route in ("/icon-180.png", "/icon-192.png", "/icon-512.png"):
                p = APP_DIR / "ui" / route.lstrip("/")
                if p.is_file():
                    self._send(200, p.read_bytes(), "image/png")
                else:
                    self._json({"error": "not found"}, 404)
            elif route == "/manifest.webmanifest":
                p = APP_DIR / "ui" / "manifest.webmanifest"
                self._send(200, p.read_bytes(), "application/manifest+json; charset=utf-8")
            elif route == "/api/summary":
                self._json(self.api_summary())
            elif route == "/api/timeseries":
                self._json(self.api_timeseries())
            elif route == "/api/reports":
                self._json(self.api_reports())
            elif route == "/api/report":
                self.api_report(qs)
            elif route.startswith("/api/report/"):
                self.api_report_path(route[len("/api/report/"):])
            elif route == "/api/status":
                self._json(self.api_status())
            elif route == "/api/runlog":
                self._json(self.api_runlog())
            elif route == "/api/sov":
                self._json(self.api_sov())
            elif route == "/api/luxury":
                self._json(self.api_luxury())
            elif route == "/api/events":
                self._json(self.api_events())
            elif route == "/api/pool":
                self._json(self.api_pool())
            elif route == "/api/news":
                self._json(self.api_news())
            elif route == "/api/calendar":
                self._json(self.api_dated_file("calendar"))
            elif route == "/api/ambassadors":
                self._json(self.api_dated_file("ambassadors"))
            elif route == "/api/products":
                self._json(self.api_dated_file("products"))
            elif route.startswith("/product-images/"):
                self.serve_product_image(route[len("/product-images/"):])
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:  # keep the app alive on any handler bug
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    def api_summary(self):
        idx_dir = self.root / "data" / "index"
        snaps = sorted(p for p in idx_dir.glob("*.json") if DATE_RE.match(p.stem))
        if not snaps:
            return {"has_data": False}
        with open(snaps[-1], "r", encoding="utf-8") as f:
            snap = json.load(f)
        snap["has_data"] = True
        snap["snapshot_count"] = len(snaps)
        return snap

    def api_timeseries(self):
        csv_path = self.root / "data" / "index" / "gmai_timeseries.csv"
        rows = []
        if csv_path.exists():
            with open(csv_path, "r", encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    try:
                        rows.append({"date": r["date"], "region": r["region"],
                                     "GMAI": float(r["GMAI"]), "band": r.get("band", "")})
                    except (KeyError, TypeError, ValueError):
                        continue
        return {"rows": rows}

    def api_reports(self):
        out = []
        base = self.root / "data" / "reports"
        for cat in REPORT_CATEGORIES:
            d = base / cat
            if not d.exists():
                continue
            for p in d.glob("*.md"):
                if "news-scrap" in p.stem:  # news is raw material, not an analysis report
                    continue
                if p.stem.endswith("-en"):  # English editions are variants, not separate reports
                    continue
                out.append({
                    "category": cat,
                    "name": p.stem,
                    "path": f"{cat}/{p.name}",
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
        out.sort(key=lambda r: r["mtime"], reverse=True)
        return {"reports": out}

    def api_report(self, qs):
        rel = (qs.get("p") or [""])[0]
        lang = (qs.get("lang") or ["ko"])[0]
        base = (self.root / "data" / "reports").resolve()
        target = (base / rel).resolve()
        if not str(target).startswith(str(base)) or target.suffix != ".md" or not target.exists():
            self._json({"error": "invalid report path"}, 400)
            return
        # A report is ONE file; an optional English edition follows the marker.
        marker = "<!-- ===== ENGLISH EDITION ===== -->"
        content = target.read_text(encoding="utf-8")
        lang_used = "ko"
        if marker in content:
            ko_part, en_part = content.split(marker, 1)
            if lang == "en" and en_part.strip():
                content, lang_used = en_part.strip(), "en"
            else:
                content = ko_part.rstrip()
        self._json({"path": rel, "lang": lang_used, "content": content})

    def api_report_path(self, rel):
        """Path-based report fetch returning the FULL file (client splits KO/EN).
        Static-hosting friendly: no query strings."""
        from urllib.parse import unquote
        rel = unquote(rel)
        base = (self.root / "data" / "reports").resolve()
        target = (base / rel).resolve()
        if not str(target).startswith(str(base)) or target.suffix != ".md" or not target.exists():
            self._json({"error": "invalid report path"}, 400)
            return
        self._json({"path": rel, "content": target.read_text(encoding="utf-8")})

    def api_status(self):
        try:
            ui_mtime = int((APP_DIR / "ui" / "index.html").stat().st_mtime)
        except OSError:
            ui_mtime = 0
        with RUN_LOCK:
            proc = RUN_STATE["proc"]
            running = proc is not None and proc.poll() is None
            if proc is not None and proc.poll() is not None and RUN_STATE["exit"] is None:
                RUN_STATE["exit"] = proc.poll()
            cmd, arg = RUN_STATE["cmd"], RUN_STATE["arg"]
            started, exitc, logn = RUN_STATE["started"], RUN_STATE["exit"], RUN_STATE["log"]
        if not running:  # a run may be owned by the sibling server instance
            other = self._lock_read()
            if other:
                running, cmd, arg = True, other.get("cmd"), ""
                started, exitc, logn = other.get("started"), None, other.get("log")
        auth_error = False
        if not running and logn:
            logp = self.root / "logs" / logn
            if logp.exists():
                try:
                    tail = logp.read_text(encoding="utf-8", errors="replace")[-2000:]
                    auth_error = "Failed to authenticate" in tail or "Invalid authentication" in tail
                except OSError:
                    pass
        return {
            "ui_mtime": ui_mtime,
            "auth_error": auth_error,
            "running": running,
            "cmd": cmd,
            "arg": arg,
            "started": started,
            "exit": exitc,
            "log": logn,
            "readonly": self.readonly,
            "key_required": self.readonly,
            "claude_available": shutil.which("claude") is not None,
            "root": "" if self.readonly else str(self.root),
        }

    def api_runlog(self):
        if self.readonly and not self._key_ok():
            return {"lines": []}
        with RUN_LOCK:
            log = RUN_STATE["log"]
        if not log:
            other = self._lock_read()
            if other:
                log = other.get("log")
        if not log:
            return {"lines": []}
        p = self.root / "logs" / log
        if not p.exists():
            return {"lines": []}
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        return {"lines": lines[-200:]}

    def _latest_date_dir(self, base):
        if not base.exists():
            return None
        dates = sorted(p.name for p in base.iterdir() if p.is_dir() and DATE_RE.match(p.name))
        return dates[-1] if dates else None

    def api_sov(self):
        # Prefer the objective symmetric-search counts (data/sov/{DATE}.json);
        # fall back to collection-derived mention_counts, flagged as biased.
        sov_base = self.root / "data" / "sov"
        files = sorted(p for p in sov_base.glob("*.json") if DATE_RE.match(p.stem)) if sov_base.exists() else []
        if files:
            try:
                with open(files[-1], "r", encoding="utf-8") as f:
                    data = json.load(f)
                counts = {}
                for region_counts in (data.get("regions") or {}).values():
                    for k, v in (region_counts or {}).items():
                        counts[k] = counts.get(k, 0) + (v or 0)
                if counts:
                    return {"has_data": True, "date": data.get("date", files[-1].stem),
                            "counts": counts, "source": "objective",
                            "regions": data.get("regions"),
                            "method": data.get("method"), "window": data.get("window"),
                            "material": data.get("material"),
                            "criteria": data.get("criteria"), "criteria_en": data.get("criteria_en"),
                            "query_template": data.get("query_template"),
                            "count_basis": data.get("count_basis"),
                            "evidence": data.get("evidence")}
            except (OSError, json.JSONDecodeError):
                pass
        base = self.root / "data" / "raw"
        date = self._latest_date_dir(base)
        if not date:
            return {"has_data": False}
        counts = {}
        for f in (base / date).glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue
            mc = data.get("mention_counts") if isinstance(data, dict) else None
            for k, v in (mc or {}).items():
                counts[k] = counts.get(k, 0) + (v or 0)
        return {"has_data": bool(counts), "date": date, "counts": counts, "source": "collection-derived"}

    def api_luxury(self):
        base = self.root / "data" / "luxury"
        date = self._latest_date_dir(base)
        if not date:
            return {"has_data": False}
        groups = {}
        for f in sorted((base / date).glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                items = data.get("findings") or data.get("items") or []
                if not items:
                    # Schema guard: flatten drifted category sub-lists
                    # (top_stories / shows_launches / financial ...) so the
                    # Luxury Watch tab never renders a collected group as 0.
                    seen = set()
                    for k, v in data.items():
                        if k in ("brand_group", "date", "mode", "generated_at",
                                 "watch_summary") or not isinstance(v, list):
                            continue
                        for it in v:
                            if not isinstance(it, dict):
                                continue
                            it.setdefault("url", it.get("source_url", ""))
                            key = it.get("url") or it.get("headline")
                            if key in seen:
                                continue
                            seen.add(key)
                            items.append(it)
            else:
                items = data
            groups[f.stem] = items if isinstance(items, list) else []
        return {"has_data": bool(groups), "date": date, "groups": groups}

    def api_events(self):
        out, known = [], set()
        evroot = self.root / "data" / "events"
        repdir = self.root / "data" / "reports" / "events"
        if evroot.exists():
            for d in sorted(evroot.iterdir()):
                if not d.is_dir():
                    continue
                known.add(d.name)
                cps = []
                for p in sorted(d.glob("*.json"), key=lambda q: q.stat().st_mtime):
                    rep = repdir / f"{d.name}-{p.stem}.md"
                    cps.append({
                        "checkpoint": p.stem,
                        "report": f"events/{rep.name}" if rep.exists() else None,
                        "mtime": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                    })
                out.append({"event_id": d.name, "checkpoints": cps})
        if repdir.exists():
            for p in sorted(repdir.glob("*.md")):
                eid = re.sub(r"-T\+[^-]+$", "", p.stem)
                if eid in known:
                    continue
                out.append({"event_id": eid, "checkpoints": [{
                    "checkpoint": p.stem[len(eid) + 1:] if p.stem.startswith(eid + "-") else p.stem,
                    "report": f"events/{p.name}",
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                }]})
        return {"events": out}

    def api_pool(self):
        p = self.root / "data" / "sources" / "pool.json"
        if not p.exists():
            return {"error": "pool.json missing"}
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def api_dated_file(self, kind):
        base = self.root / "data" / kind
        files = sorted(p for p in base.glob("*.json") if DATE_RE.match(p.stem)) if base.exists() else []
        if not files:
            return {"has_data": False}
        with open(files[-1], "r", encoding="utf-8") as f:
            data = json.load(f)
        # Schema guard: subagents occasionally drift from the {"items":[...]}
        # contract. Salvage known variants so the tabs never render blank.
        if isinstance(data, dict) and not data.get("items"):
            salvaged = []
            for key in ("events", "gucci_ambassadors", "viral_moments",
                        "competitor_ambassador_moves"):
                v = data.get(key)
                if isinstance(v, list):
                    salvaged.extend(x for x in v if isinstance(x, dict))
            for it in salvaged:  # map the common alternate field names
                it.setdefault("url", it.get("source_url", ""))
                it.setdefault("action_ko", it.get("gucci_action_window", ""))
                if "name" not in it and "ambassador" in it:
                    it["name"] = it["ambassador"]
                if "what_en" not in it and "activity" in it:
                    it["what_en"] = it["activity"]
            if salvaged:
                data["items"] = salvaged
        data["has_data"] = True
        return data

    IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                   ".webp": "image/webp", ".gif": "image/gif", ".avif": "image/avif"}

    def serve_product_image(self, name):
        base = (self.root / "data" / "products" / "images").resolve()
        target = (base / name).resolve()
        ctype = self.IMAGE_TYPES.get(target.suffix.lower())
        if not str(target).startswith(str(base)) or not ctype or not target.is_file():
            self._json({"error": "not found"}, 404)
            return
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def api_news(self):
        base = self.root / "data" / "news"
        files = sorted(p for p in base.glob("*.json") if DATE_RE.match(p.stem)) if base.exists() else []
        if not files:
            return {"has_data": False}
        with open(files[-1], "r", encoding="utf-8") as f:
            data = json.load(f)
        data["has_data"] = True
        data["available_dates"] = [p.stem for p in files][-14:]
        return data

    # ---------- POST ----------

    def do_POST(self):
        parsed = urlparse(self.path)
        route = self._strip_subpath(parsed.path)
        if route != "/api/run":
            self._json({"error": "not found"}, 404)
            return
        if self.readonly and not self._key_ok():
            self._json({"error": "invalid run key"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json({"error": "bad request body"}, 400)
            return
        self.api_run(body)

    def api_run(self, body):
        cmd = str(body.get("cmd", ""))
        arg = str(body.get("arg", "")).strip()
        if cmd not in ALLOWED_CMDS:
            self._json({"error": f"unknown command: {cmd}"}, 400)
            return
        if cmd == "event-response" and not arg:
            self._json({"error": "event-response needs an event name"}, 400)
            return
        claude = shutil.which("claude")
        if not claude:
            self._json({"error": "claude CLI not found on PATH"}, 503)
            return

        if cmd == "event-response":
            prompt = f'/{cmd} "{arg}"'
        elif arg and DATE_RE.match(arg):
            prompt = f"/{cmd} {arg}"
        else:
            prompt = f"/{cmd}"

        with RUN_LOCK:
            if RUN_STATE["proc"] is not None and RUN_STATE["proc"].poll() is None:
                self._json({"error": "already running", "cmd": RUN_STATE["cmd"]}, 409)
                return
            other = self._lock_read()
            if other:
                self._json({"error": "already running", "cmd": other.get("cmd")}, 409)
                return
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            logname = f"apprun-{cmd}-{stamp}.log"
            logdir = self.root / "logs"
            logdir.mkdir(parents=True, exist_ok=True)
            logfile = open(logdir / logname, "w", encoding="utf-8")
            logfile.write(f"[{datetime.now().isoformat(timespec='seconds')}] claude -p {prompt}\n")
            logfile.flush()
            # The user-level ANTHROPIC_API_KEY belongs to the (exhausted) watcher
            # fleet; if claude CLI sees it, headless runs die with 401. Strip it and
            # inject the long-lived subscription token (registry fallback covers
            # servers started before the token existed in the parent environment).
            child_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            if "CLAUDE_CODE_OAUTH_TOKEN" not in child_env:
                try:
                    import winreg  # Windows only; cloud runners pass the env var directly
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                        child_env["CLAUDE_CODE_OAUTH_TOKEN"] = winreg.QueryValueEx(
                            key, "CLAUDE_CODE_OAUTH_TOKEN")[0]
                except Exception:
                    pass
            try:
                proc = subprocess.Popen(
                    [claude, "-p", prompt, "--dangerously-skip-permissions"],
                    cwd=str(self.root), stdout=logfile, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, env=child_env,
                )
            except OSError as e:
                logfile.close()
                self._json({"error": f"failed to launch: {e}"}, 500)
                return
            RUN_STATE.update({"proc": proc, "cmd": cmd, "arg": arg, "exit": None,
                              "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                              "log": logname})
            started_s = RUN_STATE["started"]
            try:
                self._lock_path().write_text(json.dumps(
                    {"cmd": cmd, "started": started_s, "log": logname}), encoding="utf-8")
            except OSError:
                pass
            # On completion: release the cross-process lock and, on success,
            # refresh the cloud snapshot so the GitHub Pages site stays current.
            publish = self.root / "scripts" / "publish-site.bat"
            lockp = self._lock_path()
            def _sync(p=proc, bat=str(publish), lp=lockp):
                rc = p.wait()
                try:
                    lp.unlink()
                except OSError:
                    pass
                if rc == 0 and Path(bat).exists():
                    try:
                        subprocess.Popen(["cmd", "/c", bat], cwd=str(self.root),
                                         creationflags=0x08000000)  # no window
                    except OSError:
                        pass
            threading.Thread(target=_sync, daemon=True).start()
        self._json({"ok": True, "cmd": cmd, "prompt": prompt, "log": logname})


def main():
    # Under pythonw there is no console: sys.stdout/stderr are None and any
    # print() would crash the process. Route them to a log file instead.
    if sys.stdout is None or sys.stderr is None:
        logdir = APP_DIR.parent / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        stream = open(logdir / "app-server.log", "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream
    elif sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--root", default=str(APP_DIR.parent))
    parser.add_argument("--readonly", action="store_true",
                        help="viewer mode: run APIs disabled (for public sharing)")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.project_root = Path(args.root).resolve()
    server.readonly = args.readonly
    mode = "READ-ONLY viewer" if args.readonly else "full"
    print(f"Gucci Intelligence app ({mode}): http://127.0.0.1:{args.port}/  (root={server.project_root})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
