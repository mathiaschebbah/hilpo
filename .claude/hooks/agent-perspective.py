#!/usr/bin/env python3
"""PostToolUse hook — rappelle à l'agent de mettre à jour sa perspective tous les 10 commits."""

import json
import subprocess
import sys
from pathlib import Path


PERSPECTIVE_FILE = "docs/agent_perspective.md"
COMMIT_INTERVAL = 10


def count_commits_since_last_perspective_update() -> int:
    """Compte les commits depuis la dernière modification de agent_perspective.md."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-- {PERSPECTIVE_FILE}"],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
        )
        if not result.stdout.strip():
            return 999  # jamais mis à jour

        last_hash = result.stdout.strip().split("\n")[0].split()[0]

        result2 = subprocess.run(
            ["git", "rev-list", "--count", f"{last_hash}..HEAD"],
            capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
        )
        return int(result2.stdout.strip())
    except Exception:
        return 0


def main():
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    if tool_name != "Bash" or "git" not in command or "commit" not in command:
        print(json.dumps({}))
        return

    commits_since = count_commits_since_last_perspective_update()

    if commits_since >= COMMIT_INTERVAL:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "notification": (
                    f"**Agent Perspective** : {commits_since} commits depuis la dernière mise à jour "
                    f"de `{PERSPECTIVE_FILE}`. "
                    "Ajoute une nouvelle section datée avec ton état de compréhension actuel du projet, "
                    "les décisions récentes, et les dynamiques de collaboration observées."
                ),
            }
        }))
    else:
        print(json.dumps({}))


if __name__ == "__main__":
    main()
