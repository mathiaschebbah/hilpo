"""Render le contexte exact envoyé au LLM pour un post donné.

Utilise les MÊMES fonctions que la pipeline (build_simple_messages /
build_alma_descriptor_messages + classifier messages), donc si le rendu
est correct ici, il l'est aussi en production.

Usage :
  uv run python scripts/render_context.py POST_ID [--simple|--alma] [--no-assist]
  uv run python scripts/render_context.py POST_ID --simple --no-assist --inspect

Par défaut : mode simple no-ASSIST (config du run 165 Pareto-optimal alpha).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg
from psycopg.rows import dict_row

from milpo.agent_common import build_simple_messages


DSN = os.environ.get(
    "HILPO_DATABASE_DSN",
    "postgresql://hilpo:hilpo@localhost:5433/hilpo",
)


def fetch_post(post_id: int) -> dict:
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        row = conn.execute(
            """
            SELECT ig_media_id, caption, media_product_type, timestamp AS posted_at
            FROM posts
            WHERE ig_media_id = %s
            """,
            (post_id,),
        ).fetchone()
        if not row:
            raise SystemExit(f"Post {post_id} introuvable en BDD")

        media = conn.execute(
            """
            SELECT media_url, media_type, media_order
            FROM post_media
            WHERE parent_ig_media_id = %s
            ORDER BY media_order
            """,
            (post_id,),
        ).fetchall()

    row["media_urls"] = [m["media_url"] for m in media]
    row["media_types"] = [m["media_type"] for m in media]
    return row


def sha256_short(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("post_id", type=int, help="ig_media_id du post")
    ap.add_argument("--simple", action="store_true", default=True,
                    help="Mode simple (défaut)")
    ap.add_argument("--no-assist", action="store_true",
                    help="Sans questions ASSIST (config Pareto winner run 165)")
    ap.add_argument("--inspect", action="store_true",
                    help="Affiche bloc par bloc avec tailles et hash")
    ap.add_argument("--raw", action="store_true",
                    help="Dump brut du system + user text (pas les images)")
    ap.add_argument("--json", action="store_true",
                    help="Sortie JSON structurée")
    args = ap.parse_args()

    post = fetch_post(args.post_id)

    messages = build_simple_messages(
        media_urls=post["media_urls"],
        media_types=post["media_types"],
        caption=post["caption"],
        post_scope=post["media_product_type"],
        posted_at=post["posted_at"],
        no_assist=args.no_assist,
    )

    system_text = messages[0]["content"]
    user_content = messages[1]["content"]

    text_blocks = [b for b in user_content if b.get("type") == "text"]
    image_blocks = [b for b in user_content if b.get("type") == "image_url"]

    user_intro = text_blocks[0]["text"] if text_blocks else ""
    user_outro = text_blocks[1]["text"] if len(text_blocks) > 1 else ""

    if args.json:
        import json as jsonlib
        out = {
            "post_id": args.post_id,
            "scope": post["media_product_type"],
            "mode": "simple_no_assist" if args.no_assist else "simple_assist",
            "system": {
                "length": len(system_text),
                "sha256_16": sha256_short(system_text),
                "text": system_text,
            },
            "user_intro": {
                "length": len(user_intro),
                "sha256_16": sha256_short(user_intro),
                "text": user_intro,
            },
            "images_count": len(image_blocks),
            "user_outro": {
                "length": len(user_outro),
                "text": user_outro,
            },
            "total_template_sha256": sha256_short(system_text + user_intro),
        }
        print(jsonlib.dumps(out, ensure_ascii=False, indent=2))
        return

    if not args.raw:
        mode_label = "simple no-ASSIST" if args.no_assist else "simple ASSIST"
        print(f"╭─ CONTEXTE RENDU — post {args.post_id} ({post['media_product_type']}) ─ mode {mode_label}")
        print(f"│  template hash : {sha256_short(system_text + user_intro)}")
        print(f"│  caption       : {len(post['caption'] or '')} chars")
        print(f"│  images        : {len(image_blocks)}")
        print("╰─────────────────────────────────────────────────────────────")
        print()

    if args.inspect:
        print(f"━━ SYSTEM ({len(system_text)} chars, sha={sha256_short(system_text)}) ━━")
        print(system_text)
        print()
        print(f"━━ USER INTRO ({len(user_intro)} chars, sha={sha256_short(user_intro)}) ━━")

        blocks = split_intro_into_blocks(user_intro)
        for name, body in blocks:
            body_preview = body[:120].replace("\n", " ⏎ ")
            print(f"  • {name:30s} {len(body):5d} chars  │ {body_preview}...")
        print()
        print(f"━━ IMAGES ({len(image_blocks)}) ━━")
        for i, img in enumerate(image_blocks, 1):
            url = img["image_url"]["url"]
            print(f"  [{i}] {url[:80]}...")
        print()
        print(f"━━ USER OUTRO ({len(user_outro)} chars) ━━")
        print(user_outro)
    elif args.raw:
        # Strict : ce que le LLM reçoit, avec seulement les markers de tour OpenAI.
        print("<|system|>")
        print(system_text)
        print("<|user|>")
        print(user_intro)
        for img in image_blocks:
            print(f"<image url=\"{img['image_url']['url']}\"/>")
        print(user_outro)
    else:
        print("Aperçu (--inspect pour blocs détaillés, --raw pour tout, --json pour structure) :")
        print()
        print(f"SYSTEM  ({len(system_text)} chars)")
        print(f"USER    ({len(user_intro) + len(user_outro)} chars + {len(image_blocks)} images)")
        print()
        print(f"Début du user intro :")
        print(user_intro[:400] + "..." if len(user_intro) > 400 else user_intro)


def split_intro_into_blocks(intro: str) -> list[tuple[str, str]]:
    """Découpe l'intro user par headers connus."""
    HEADERS = [
        ("Grille d'observation :",      "GRILLE ASSIST"),
        ("Descriptions des classes — axe visual_format :", "TAXONOMIE VF"),
        ("Descriptions des classes — axe category :",      "TAXONOMIE CAT"),
        ("Descriptions des classes — axe strategy :",      "TAXONOMIE STRAT"),
        ("NON NÉGOCIABLE - Suis cette procédure",          "PROCÉDURES"),
        ("Voici le média :",            "MÉDIA LABEL"),
    ]
    positions = []
    for key, name in HEADERS:
        idx = intro.find(key)
        if idx >= 0:
            positions.append((idx, name))
    positions.sort()
    blocks = []
    for i, (start, name) in enumerate(positions):
        end = positions[i+1][0] if i+1 < len(positions) else len(intro)
        blocks.append((name, intro[start:end]))
    return blocks


if __name__ == "__main__":
    main()
