"""Agent rewriter HILPO — analyse les erreurs et propose un nouveau prompt."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from openai import OpenAI

from hilpo.client import get_client
from hilpo.config import MODEL_REWRITER
from hilpo.errors import LLMCallError
from hilpo.schemas import RewritePayload, build_json_schema_response_format

log = logging.getLogger("hilpo")

MAX_SYNC_RETRIES = 3


def _sleep_before_retry(attempt: int) -> None:
    """Backoff exponentiel simple pour les appels sync."""
    time.sleep(2 ** attempt)

REWRITER_SYSTEM = """\
Tu es un ingénieur prompt expert du pipeline de classification de contenus Instagram.

Tu reçois :
1. Les **instructions actuelles** d'un agent du pipeline (descripteur multimodal ou agent de classification)
2. Un **batch d'erreurs** : pour chaque erreur, le label prédit, le label attendu (annotation humaine), les features visuelles extraites, la caption, et les descriptions taxonomiques des deux labels
3. Les **descriptions taxonomiques complètes** de tous les labels du scope

## Ta mission

Analyse les patterns d'erreur dans le batch et réécris les instructions pour corriger ces erreurs. Tu dois :

1. **Diagnostiquer** : quelles règles ou heuristiques dans les instructions actuelles causent les erreurs ? Quels patterns visuels/textuels sont mal interprétés ou mal extraits ?
2. **Corriger** : modifier les règles de décision ou d'extraction, ajouter des cas spécifiques, clarifier les frontières entre labels confondus
3. **Préserver** : ne pas casser ce qui fonctionne. Les instructions doivent rester cohérentes et complètes.

## Contraintes

- Les nouvelles instructions remplacent entièrement les anciennes (pas un diff)
- Garde le même format et style que les instructions originales
- Ne modifie PAS les descriptions taxonomiques (elles sont fixes)
- Sois concis dans les instructions — le prompt sera envoyé à chaque classification
"""


@dataclass
class ErrorCase:
    """Une erreur de classification à analyser."""

    ig_media_id: int
    axis: str
    prompt_scope: str | None
    post_scope: str
    predicted: str
    expected: str
    features_json: str
    caption: str | None
    desc_predicted: str
    desc_expected: str


@dataclass
class RewriteResult:
    """Résultat d'un appel au rewriter."""

    new_instructions: str
    reasoning: str
    target_agent: str
    target_scope: str | None
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


def _format_error_batch(errors: list[ErrorCase]) -> str:
    """Formate le batch d'erreurs pour le prompt du rewriter."""
    lines = []
    for i, e in enumerate(errors, 1):
        lines.append(f"### Erreur {i}")
        lines.append(f"- **Axe concerné** : `{e.axis}`")
        lines.append(f"- **Scope du post** : `{e.post_scope}`")
        lines.append(f"- **Prédit** : `{e.predicted}`")
        lines.append(f"- **Attendu** : `{e.expected}`")
        lines.append(f"- **Caption** : {(e.caption or '(vide)')[:300]}")
        lines.append(f"- **Description label prédit** : {e.desc_predicted}")
        lines.append(f"- **Description label attendu** : {e.desc_expected}")
        lines.append(f"- **Features extraites** :\n```json\n{e.features_json[:1500]}\n```")
        lines.append("")
    return "\n".join(lines)


def rewrite_prompt(
    target_agent: str,
    target_scope: str | None,
    current_instructions: str,
    errors: list[ErrorCase],
    all_descriptions: str,
    model: str = MODEL_REWRITER,
    client: OpenAI | None = None,
) -> RewriteResult:
    """Appelle le rewriter pour proposer un nouveau prompt.

    Args:
        current_instructions: Instructions I_t actuelles du prompt ciblé.
        errors: Batch d'erreurs filtrées pour la cible.
        all_descriptions: Descriptions taxonomiques complètes du scope.
        model: Modèle LLM à utiliser.
        client: Client OpenAI (créé si None).

    Returns:
        RewriteResult avec les nouvelles instructions et le raisonnement.
    """
    if client is None:
        client = get_client()

    target_label = f"{target_agent}/{target_scope}" if target_scope else f"{target_agent}/all"

    user_content = f"""## Cible du rewrite

{target_label}

## Instructions actuelles

```
{current_instructions}
```

## Batch d'erreurs ({len(errors)} erreurs)

{_format_error_batch(errors)}

## Descriptions taxonomiques (référence)

{all_descriptions}

---

Analyse les erreurs et propose des instructions améliorées."""

    t0 = time.perf_counter()
    last_error: Exception | None = None
    response_format = build_json_schema_response_format(
        "rewriter_payload",
        RewritePayload.model_json_schema(),
    )

    for attempt in range(MAX_SYNC_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": REWRITER_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
                response_format=response_format,
                temperature=0.3,
            )

            if not response.choices:
                raise RuntimeError("Rewriter: réponse vide")

            content = response.choices[0].message.content or ""
            if not content:
                raise RuntimeError("Rewriter: content vide")

            payload = RewritePayload.model_validate_json(content)

            latency_ms = int((time.perf_counter() - t0) * 1000)
            return RewriteResult(
                new_instructions=payload.new_instructions,
                reasoning=payload.reasoning,
                target_agent=target_agent,
                target_scope=target_scope,
                model=model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            last_error = exc
            log.warning("Rewriter appel échoué (attempt %d/%d): %s",
                        attempt + 1, MAX_SYNC_RETRIES, exc)
            if attempt < MAX_SYNC_RETRIES - 1:
                _sleep_before_retry(attempt)
                continue

    raise LLMCallError("Rewriter: épuisé les retries") from last_error
