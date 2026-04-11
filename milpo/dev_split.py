"""Split déterministe 70/30 des posts dev en dev-opt / dev-holdout.

Le split est stratifié par scope (FEED/REELS) et par label visual_format.
Les classes rares (count < 3 dans le split) sont forcées dans dev-opt
pour que l'optimiseur puisse les voir.
"""

from __future__ import annotations

import logging
import random
from collections import Counter, defaultdict

log = logging.getLogger("milpo")


def create_dev_split(
    conn,
    seed: int = 42,
    opt_fraction: float = 0.70,
) -> dict[str, list[int]]:
    """Crée et persiste le split dev-opt / dev-holdout.

    Idempotent : si le split existe déjà en BDD, le retourne sans modifier.

    Returns:
        {"dev_opt": [ig_media_id, ...], "dev_holdout": [ig_media_id, ...]}
    """
    from milpo.db.rules import count_dev_split, insert_dev_split_assignments, load_dev_split_assignments

    existing = load_dev_split_assignments(conn)
    if existing:
        log.info("Dev split déjà existant (%d posts), réutilisation.", len(existing))
        result: dict[str, list[int]] = {"dev_opt": [], "dev_holdout": []}
        for pid, split in existing.items():
            result[split].append(pid)
        return result

    rows = conn.execute(
        """
        SELECT a.ig_media_id, p.media_product_type,
               vf.name AS visual_format
        FROM annotations a
        JOIN posts p ON p.ig_media_id = a.ig_media_id
        JOIN visual_formats vf ON vf.id = a.visual_format_id
        JOIN sample_posts sp ON sp.ig_media_id = a.ig_media_id
        WHERE sp.split = 'dev'
        ORDER BY a.ig_media_id
        """
    ).fetchall()

    if not rows:
        raise RuntimeError("Aucun post dev annoté en BDD.")

    by_scope: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_scope[row["media_product_type"]].append(row)

    rng = random.Random(seed)
    assignments: list[tuple[int, str]] = []

    for scope, scope_rows in sorted(by_scope.items()):
        by_vf: dict[str, list[int]] = defaultdict(list)
        for row in scope_rows:
            by_vf[row["visual_format"]].append(row["ig_media_id"])

        opt_ids: list[int] = []
        holdout_ids: list[int] = []

        for vf_label, pids in sorted(by_vf.items()):
            if len(pids) < 3:
                opt_ids.extend(pids)
                continue

            shuffled = list(pids)
            rng.shuffle(shuffled)
            n_opt = max(1, round(len(shuffled) * opt_fraction))
            opt_ids.extend(shuffled[:n_opt])
            holdout_ids.extend(shuffled[n_opt:])

        for pid in opt_ids:
            assignments.append((pid, "dev_opt"))
        for pid in holdout_ids:
            assignments.append((pid, "dev_holdout"))

    insert_dev_split_assignments(conn, assignments)

    result = {"dev_opt": [], "dev_holdout": []}
    for pid, split in assignments:
        result[split].append(pid)

    log.info(
        "Dev split créé : %d dev-opt, %d dev-holdout (seed=%d, fraction=%.0f%%)",
        len(result["dev_opt"]),
        len(result["dev_holdout"]),
        seed,
        opt_fraction * 100,
    )
    return result


def load_dev_split(conn) -> dict[str, list[int]]:
    """Charge le split existant. Raise si pas encore créé."""
    from milpo.db.rules import load_dev_split_assignments

    existing = load_dev_split_assignments(conn)
    if not existing:
        raise RuntimeError("Dev split non créé. Appeler create_dev_split() d'abord.")

    result: dict[str, list[int]] = {"dev_opt": [], "dev_holdout": []}
    for pid, split in existing.items():
        result[split].append(pid)
    return result


def audit_dev_split(conn) -> dict:
    """Rapport d'audit du split : couverture des classes, équilibre, etc."""
    from milpo.db.rules import load_dev_split_assignments

    assignments = load_dev_split_assignments(conn)
    if not assignments:
        return {"error": "Aucun split trouvé"}

    opt_ids = {pid for pid, s in assignments.items() if s == "dev_opt"}
    holdout_ids = {pid for pid, s in assignments.items() if s == "dev_holdout"}

    rows = conn.execute(
        """
        SELECT a.ig_media_id, p.media_product_type, vf.name AS visual_format
        FROM annotations a
        JOIN posts p ON p.ig_media_id = a.ig_media_id
        JOIN visual_formats vf ON vf.id = a.visual_format_id
        JOIN sample_posts sp ON sp.ig_media_id = a.ig_media_id
        WHERE sp.split = 'dev'
        """
    ).fetchall()

    opt_vf: list[str] = []
    holdout_vf: list[str] = []
    opt_scope: Counter[str] = Counter()
    holdout_scope: Counter[str] = Counter()

    for row in rows:
        pid = row["ig_media_id"]
        if pid in opt_ids:
            opt_vf.append(row["visual_format"])
            opt_scope[row["media_product_type"]] += 1
        elif pid in holdout_ids:
            holdout_vf.append(row["visual_format"])
            holdout_scope[row["media_product_type"]] += 1

    opt_classes = set(opt_vf)
    holdout_classes = set(holdout_vf)
    missing_from_holdout = opt_classes - holdout_classes
    missing_from_opt = holdout_classes - opt_classes

    return {
        "n_opt": len(opt_ids),
        "n_holdout": len(holdout_ids),
        "ratio_opt": len(opt_ids) / (len(opt_ids) + len(holdout_ids)),
        "opt_scope": dict(opt_scope),
        "holdout_scope": dict(holdout_scope),
        "opt_vf_classes": len(opt_classes),
        "holdout_vf_classes": len(holdout_classes),
        "missing_from_holdout": sorted(missing_from_holdout),
        "missing_from_opt": sorted(missing_from_opt),
    }
