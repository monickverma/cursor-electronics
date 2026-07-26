#!/usr/bin/env python3
"""
snapshot.py — Bundles the bootstrap files into a single paste-ready text block
for sharing memory with Claude.ai (when not using Drive/GitHub sync).

Run:
    python tools/snapshot.py              # prints to stdout
    python tools/snapshot.py --clipboard  # copies to clipboard (macOS/Linux)
    python tools/snapshot.py -o snap.md   # writes to file

Then paste the output into Claude.ai. The model gets the same memory as Claude Code.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Files to include in the snapshot, in read order.
# Tweak this list if you want a leaner or fuller snapshot.
BOOTSTRAP_FILES = [
    "AGENTS.md",
    "brain/vision.md",
    "brain/architecture.md",
    "plan/current_phase.md",
    "state.json",
    "progress.yaml",
]

# Optional: include these if you have token budget
OPTIONAL_FILES = [
    "brain/decisions.md",
    "brain/knowledge.md",
    "brain/timeline.md",
    "plan/master_plan.md",
]


def get_git_status():
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=5
        ).stdout.strip()
        log = subprocess.run(
            ["git", "log", "-5", "--oneline"],
            cwd=ROOT, capture_output=True, text=True, timeout=5
        ).stdout.strip()
        return commit, log
    except Exception:
        return "unknown", ""


def render_file(path: Path) -> str:
    rel = path.relative_to(ROOT)
    if not path.exists():
        return f"\n\n=== {rel} ===\n[FILE DOES NOT EXIST]\n"
    content = path.read_text()
    return f"\n\n=== {rel} ===\n\n{content}"


def build_snapshot(include_optional: bool = False) -> str:
    commit, log = get_git_status()

    header = f"""# Project Snapshot — paste into Claude.ai

You are joining an existing project. Read everything below before answering.
Follow the bootstrap in AGENTS.md.

Current commit: {commit}
Recent commits:
{log}

---
"""

    files = list(BOOTSTRAP_FILES)
    if include_optional:
        files.extend(OPTIONAL_FILES)

    parts = [header]
    for f in files:
        parts.append(render_file(ROOT / f))

    parts.append("\n\n---\nEnd of snapshot. You now have full project context.")
    return "".join(parts)


def copy_to_clipboard(text: str) -> bool:
    """Try macOS pbcopy, then Linux xclip/xsel."""
    for cmd in (["pbcopy"], ["xclip", "-selection", "clipboard"], ["xsel", "-bi"]):
        try:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            p.communicate(input=text.encode())
            if p.returncode == 0:
                return True
        except FileNotFoundError:
            continue
    return False


def main():
    parser = argparse.ArgumentParser(description="Bundle bootstrap files for Claude.ai")
    parser.add_argument("--clipboard", "-c", action="store_true",
                        help="Copy snapshot to system clipboard")
    parser.add_argument("--output", "-o", help="Write snapshot to a file")
    parser.add_argument("--full", "-f", action="store_true",
                        help="Include optional files (decisions, knowledge, timeline, master_plan)")
    args = parser.parse_args()

    snapshot = build_snapshot(include_optional=args.full)
    size_kb = len(snapshot.encode()) / 1024

    if args.clipboard:
        if copy_to_clipboard(snapshot):
            print(f"✅ Snapshot copied to clipboard ({size_kb:.1f} KB)")
            print("   Paste into Claude.ai to give it full project context.")
        else:
            print("⚠ Could not access clipboard. Falling back to stdout.")
            print(snapshot)
    elif args.output:
        Path(args.output).write_text(snapshot)
        print(f"✅ Snapshot written to {args.output} ({size_kb:.1f} KB)")
    else:
        print(snapshot)
        print(f"\n[snapshot size: {size_kb:.1f} KB]", file=sys.stderr)


if __name__ == "__main__":
    main()
