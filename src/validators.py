"""
Deterministische Strukturprüfungen für den Entwurf des Architekten.
"""

import re
from typing import Any, Dict, List, Set, Tuple

# Standard stopwords excluded during tokenization to prevent spurious overlaps.
STOPWORDS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einen",
    "und", "oder", "ist", "sind", "wird", "werden", "soll", "sollen", "muss",
    "müssen", "kann", "können", "für", "mit", "von", "auf", "als", "bei",
    "the", "and", "for", "with", "from", "that", "this", "will", "shall",
    "must", "can", "should", "into", "onto",
}

MIN_TOKEN_LEN = 4  # Ignores short noisy tokens that could lead to false-positive matches.


def _tokenize(text: str) -> Set[str]:
    """Extracts unique lowercase alphabetic words exceeding the minimum length threshold."""
    words = re.findall(r"[a-zA-ZäöüÄÖÜß]+", text.lower())
    return {w for w in words if len(w) >= MIN_TOKEN_LEN and w not in STOPWORDS}


def _related(token_a: str, token_b: str) -> bool:
    """
    Fuzzy string matching heuristic checking for exact matches, substrings, 
    or significant common prefix overlap.
    """
    if token_a == token_b:
        return True
    if token_a in token_b or token_b in token_a:
        return True

    common_prefix_len = 0
    for char_a, char_b in zip(token_a, token_b):
        if char_a == char_b:
            common_prefix_len += 1
        else:
            break

    shorter_len = min(len(token_a), len(token_b))
    threshold = max(4, int(shorter_len * 0.6))
    return common_prefix_len >= threshold


def _collect_strings(obj: Any) -> List[str]:
    """Recursively walks nested JSON structures (dicts/lists) to extract all string values."""
    found: List[str] = []
    if isinstance(obj, str):
        found.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            found.extend(_collect_strings(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_collect_strings(item))
    return found


def _all_tokens(obj: Any) -> Set[str]:
    """Gathers and tokenizes every string value found within an arbitrary data structure."""
    tokens: Set[str] = set()
    for s in _collect_strings(obj):
        tokens |= _tokenize(s)
    return tokens


def check_nutzereingaben_haben_felder(
    process_definition: Dict[str, Any], design: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Ensures every atomic action in the process definition has a corresponding
    entity field, UI element, or workflow trigger referenced in the low-code design.
    """
    design_tokens = _all_tokens(design)
    missing: List[str] = []

    for step in process_definition.get("prozessschritte", []) or []:
        action_text = str(step.get("aktion", ""))
        action_tokens = _tokenize(action_text)
        if not action_tokens:
            continue  # nichts Sinnvolles für diesen Schritt zu prüfen

        has_match = any(
            _related(a_tok, d_tok) for a_tok in action_tokens for d_tok in design_tokens
        )
        if not has_match:
            missing.append(
                f"Schritt {step.get('schritt')} ('{action_text}') hat keine entsprechende "
                f"Referenz irgendwo im Entwurf (keine passende Entität, kein Feld, "
                f"kein UI-Element und kein Workflow erwähnt diese Aktion)."
            )

    return (len(missing) == 0), missing


def check_workflows_nach_trigger_getrennt(
    process_definition: Dict[str, Any], design: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Verifies that distinct operational conditions/triggers from the process definition
    are mapped to separate workflow routines in the generated design.
    """
    trigger_texts = [
        str(step.get("trigger_oder_bedingung") or "").strip()
        for step in process_definition.get("prozessschritte", []) or []
    ]
    distinct_triggers = {t for t in trigger_texts if t}

    workflows = design.get("workflows", []) or []
    workflow_trigger_tokens = [_tokenize(str(w.get("trigger", ""))) for w in workflows]

    missing: List[str] = []
    for trigger in distinct_triggers:
        trigger_tokens = _tokenize(trigger)
        if not trigger_tokens:
            continue
        matched = any(
            any(_related(t_tok, w_tok) for t_tok in trigger_tokens for w_tok in wf_tokens)
            for wf_tokens in workflow_trigger_tokens
        )
        if not matched:
            missing.append(
                f"Trigger '{trigger}' hat keinen passenden Workflow im Entwurf."
            )

    return (len(missing) == 0), missing


def run_structural_checks(process_definition: Dict[str, Any], design: Dict[str, Any]) -> Dict[str, Any]:
    """Runs all deterministic structural checks and aggregates validation results and missing elements."""
    felder_ok, felder_fehlend = check_nutzereingaben_haben_felder(process_definition, design)
    workflows_ok, workflows_fehlend = check_workflows_nach_trigger_getrennt(process_definition, design)

    return {
        "pruefungen": {
            "nutzereingaben_haben_felder": felder_ok,
            "workflows_nach_trigger_getrennt": workflows_ok,
        },
        "fehlende_details": felder_fehlend + workflows_fehlend,
    }
