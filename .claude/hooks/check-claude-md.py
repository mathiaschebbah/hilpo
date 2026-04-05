#!/usr/bin/env python3
"""PostToolUse hook — rappelle de mettre à jour CLAUDE.md après un git commit."""

import json
import sys


def main():
    input_data = json.load(sys.stdin)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    # Ne s'active que sur git commit
    if tool_name != "Bash" or not ("git" in command and "commit" in command):
        print(json.dumps({}))
        return

    # Si c'est déjà un commit docs: update CLAUDE.md, pas besoin de rappeler
    if "docs: update CLAUDE.md" in command:
        print(json.dumps({}))
        return

    message = """**Rappel : vérifie si CLAUDE.md doit être mis à jour.**

1. Revois ce qui a été fait (fichiers créés/modifiés, décisions prises, stack changée, phase avancée).
2. Utilise AskUserQuestion pour confirmer les changements à inclure (toujours proposer "Rien à mettre à jour").
3. Si confirmé : incrémente la version, ajoute au changelog, commit séparé avec `docs: update CLAUDE.md`."""

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "notification": message,
        }
    }))


if __name__ == "__main__":
    main()
