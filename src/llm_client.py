"""
LLM client for the multi-agent system — local Ollama only.
"""

import os
import re
import json
from dataclasses import dataclass
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))


@dataclass
class LLMResult:
    """Encapsulates the raw response text and the executing backend model name."""
    text: str
    backend: str 


def _call_ollama(system: str, user: str) -> str:
    """Executes a POST request to the local Ollama chat API."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.2},
        "format": "json", # Ollama native JSON-mode enforcement
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def call_llm(system: str, user: str) -> LLMResult:
    """Wrapper delivering standardized LLMResult records."""
    text = _call_ollama(system, user)
    return LLMResult(text=text, backend=f"ollama:{OLLAMA_MODEL}")


def _strip_trailing_commas(text: str) -> str:
    """Removes invalid trailing commas before closing braces/brackets."""
    return re.sub(r",(\s*[}\]])", r"\1", text)


def extract_json(text: str) -> dict:
    """Strips Markdown fences and isolates outer JSON dictionary boundaries."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        cleaned = match.group(0)
    cleaned = _strip_trailing_commas(cleaned)
    return json.loads(cleaned)


def _try_close_truncated_json(text: str) -> Optional[dict]:
    """
    Parser for truncated JSON responses.
    Balances quotes and injects missing closing brackets.
    """
    cleaned = text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    start = cleaned.find("{")
    if start == -1:
        return None
    cleaned = cleaned[start:]
    # Fix dangling quotes
    unescaped_quotes = len(re.findall(r'(?<!\\)"', cleaned))
    if unescaped_quotes % 2 == 1:
        cleaned += '"'

    # Close unbalanced braces/brackets
    opens = cleaned.count("{") + cleaned.count("[")
    closes = cleaned.count("}") + cleaned.count("]")
    missing = opens - closes
    cleaned += ("}" * missing) if missing > 0 else ""
    cleaned = _strip_trailing_commas(cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def call_llm_json(system: str, user: str, max_repair_attempts: int = 2) -> tuple[dict, str]:
    """
    Queries Ollama with automatic retry loops and structural parsing fallback routines.
    Returns parsed dictionary payload and the model backend string.
    """
    result = call_llm(system, user)
    backend = result.backend
    current_text = result.text

    last_error: Optional[Exception] = None
    for attempt in range(max_repair_attempts + 1):
        try:
            return extract_json(current_text), backend
        except (json.JSONDecodeError, AttributeError) as e:
            last_error = e

            # Attempt local repair first to save an extra roundtrip
            locally_repaired = _try_close_truncated_json(current_text)
            if locally_repaired is not None:
                return locally_repaired, backend

            if attempt == max_repair_attempts:
                break
            # Request explicit JSON schema correction from the model
            repair_prompt = (
                f"Your previous response was not valid JSON. Parse error: {e}\n\n"
                f"Previous response:\n{current_text}\n\n"
                "Respond again with ONLY a single valid JSON object. "
                "No markdown code fences, no explanation, no extra text."
            )
            repair_result = call_llm(system, repair_prompt)
            current_text = repair_result.text
            backend = repair_result.backend

    raise ValueError(
        f"Could not obtain valid JSON after {max_repair_attempts} repair attempt(s): {last_error}\n"
        f"Last raw output:\n{current_text}"
    )
