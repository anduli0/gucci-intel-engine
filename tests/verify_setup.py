#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Verify agent/command frontmatter and cross-check subagent name references."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / ".claude" / "agents"
COMMANDS_DIR = ROOT / ".claude" / "commands"
EXPECTED_AGENTS = {
    "regional-collector", "sentiment-classifier", "index-analyst",
    "business-reviewer", "event-responder", "luxury-brand-watcher",
    "trend-analyst", "daily-brief-analyst", "fact-checker", "editor-in-chief",
    "index-interpreter", "news-scout", "product-analyst", "special-analyst",
    "cd-analyst", "sov-auditor", "ambassador-tracker", "calendar-scout",
}
EXPECTED_COMMANDS = {"daily-gucci", "event-response", "weekly-luxury", "daily-brief",
                     "news-scrap", "gucci-special", "gucci-products", "cd-watch"}
VALID_MODELS = {"sonnet", "opus", "haiku", "inherit"}


def parse_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, text[m.end():]


def main():
    errors = []
    agent_names = set()

    for path in sorted(AGENTS_DIR.glob("*.md")):
        fm, _ = parse_frontmatter(path)
        if fm is None:
            errors.append(f"{path.name}: no valid frontmatter block")
            continue
        for key in ("name", "description", "tools", "model"):
            if not fm.get(key):
                errors.append(f"{path.name}: missing frontmatter key '{key}'")
        name = fm.get("name", "")
        agent_names.add(name)
        if name != path.stem:
            errors.append(f"{path.name}: name '{name}' != filename stem '{path.stem}'")
        if fm.get("model") and fm["model"] not in VALID_MODELS:
            errors.append(f"{path.name}: unexpected model '{fm['model']}'")

    if agent_names != EXPECTED_AGENTS:
        missing = EXPECTED_AGENTS - agent_names
        extra = agent_names - EXPECTED_AGENTS
        if missing:
            errors.append(f"missing agents: {sorted(missing)}")
        if extra:
            errors.append(f"unexpected agents: {sorted(extra)}")

    command_names = set()
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        if path.stem == "ultraplan":
            continue
        fm, body = parse_frontmatter(path)
        command_names.add(path.stem)
        if fm is None:
            errors.append(f"{path.name}: no valid frontmatter block")
            continue
        if not fm.get("description"):
            errors.append(f"{path.name}: missing 'description'")
        # Cross-check: every "the X subagent" reference resolves to a real agent.
        refs = set(re.findall(r"the ([a-z0-9-]+) subagent", body))
        unknown = refs - agent_names
        if unknown:
            errors.append(f"{path.name}: references unknown subagents {sorted(unknown)}")
        if not refs:
            errors.append(f"{path.name}: no explicit subagent invocations found")

    if command_names != EXPECTED_COMMANDS:
        missing = EXPECTED_COMMANDS - command_names
        extra = command_names - EXPECTED_COMMANDS
        if missing:
            errors.append(f"missing commands: {sorted(missing)}")
        if extra:
            errors.append(f"unexpected commands: {sorted(extra)}")

    print(f"agents found: {len(agent_names)} / commands found: {len(command_names)}")
    if errors:
        print("FAIL")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("PASS: all frontmatter valid; all subagent references resolve")


if __name__ == "__main__":
    main()
