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

    message = """**Rappel : vérifie si CLAUDE.md et docs/ doivent être mis à jour.**

1. Revois ce qui a été fait (fichiers créés/modifiés, décisions prises, stack changée, schéma évolué, phase avancée).
2. Vérifie si les fichiers dans `docs/` concernés doivent être mis à jour (architecture.md, phases.md, evaluation.md, schema.md, stack.md, data.md, planning.md, etc.).
3. Utilise AskUserQuestion pour confirmer les changements à inclure (toujours proposer "Rien à mettre à jour").
4. Si confirmé : mets à jour les docs/ concernés, incrémente la version CLAUDE.md, ajoute au changelog, commit séparé avec `docs: update CLAUDE.md`."""

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "notification": message,
        }
    }))


if __name__ == "__main__":
    main()
