"""Nebius Token Factory client (OpenAI-compatible chat completions).

Used for two things only:
  1. Vision text recognition — reading English/Hindi label text with bounding boxes.
  2. Plain-language explanation of a violation for the officer's UI.

It is deliberately NOT used to decide compliance. Verdicts come from the deterministic
rule engine so that, per the strategy memo, "regulation-mapped logic isn't
prompt-dependent" and every finding is reproducible and defensible in a hearing.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
from pathlib import Path

import httpx

from app.config import nebius_api_key, settings

logger = logging.getLogger(__name__)


class NebiusError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(nebius_api_key)


def _client() -> httpx.Client:
    if not nebius_api_key:
        raise NebiusError(
            "NEBIUS_API_KEY is not set. Add it to backend/.env to enable vision extraction."
        )
    return httpx.Client(
        base_url=settings.nebius_base_url.rstrip("/"),
        headers={
            "Authorization": f"Bearer {nebius_api_key}",
            "Content-Type": "application/json",
        },
        timeout=settings.nebius_timeout_seconds,
    )


def list_models() -> list[str]:
    """Live model catalogue for this account — use it to pick valid model IDs rather
    than trusting hardcoded defaults, which drift as the platform's catalogue changes.
    """
    with _client() as client:
        response = client.get("/models")
        response.raise_for_status()
        return sorted(m["id"] for m in response.json().get("data", []))


def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 2000,
    json_object: bool = False,
) -> str:
    payload: dict = {
        "model": model or settings.nebius_text_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_object:
        payload["response_format"] = {"type": "json_object"}

    with _client() as client:
        response = client.post("/chat/completions", json=payload)
        if response.status_code >= 400:
            raise NebiusError(f"Nebius {response.status_code}: {response.text[:500]}")
        data = response.json()
    return data["choices"][0]["message"]["content"]


def image_data_url(path: str | Path) -> str:
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _close_unbalanced(text: str) -> str:
    """Best-effort repair for output truncated mid-object (e.g. hit max_tokens)."""
    in_string = False
    escaped = False
    stack: list[str] = []
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    repaired = text
    if in_string:
        repaired += '"'
    for opener in reversed(stack):
        repaired += "}" if opener == "{" else "]"
    return repaired


def parse_json_response(content: str) -> dict:
    """Models occasionally wrap JSON in prose/fences, leave trailing commas, or get
    truncated mid-object; recover the intended object on a best-effort basis."""
    content = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()

    brace = re.search(r"\{.*\}", content, re.DOTALL)
    candidate = brace.group(0) if brace else content

    for attempt in (
        content,
        candidate,
        _strip_trailing_commas(candidate),
        _close_unbalanced(_strip_trailing_commas(candidate)),
    ):
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue

    logger.warning("Nebius returned unparseable JSON (%d chars): %s", len(content), content[:2000])
    raise NebiusError(f"Model did not return valid JSON: {content[:300]}")


READ_LABEL_PROMPT = """You are a text-recognition engine for a Legal Metrology inspection system.

Read ALL text visible on this packaged-commodity label, in English and Hindi (Devanagari),
exactly as printed. Do not translate, correct, summarise, or infer anything that is not
visibly printed. If text is cut off or unreadable, output what is legible and mark it.

Return ONLY a JSON object of this shape:
{
  "lines": [
    {
      "text": "<exact text of one printed line>",
      "script": "latin" | "devanagari" | "mixed",
      "bbox": {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0},
      "confidence": 0.0,
      "legible": true
    }
  ]
}

bbox values are fractions of image width/height (0-1), x/y at the top-left of the line.
confidence is your own 0-1 estimate for that line. Keep each printed line as its own entry
and preserve the label/value on one line where they are printed together
(e.g. "MRP: Rs. 45.00")."""


EXPLAIN_PROMPT = """You are assisting a Legal Metrology inspector in India.

Explain the contravention below in plain, non-technical language: what the rule requires,
what was actually found on the package, and why it matters to the consumer. Two or three
short sentences. State only what follows from the finding given. Do not offer legal advice,
do not suggest penalties, and do not invent facts about the product."""


def read_label(image_path: str | Path, lang: str = "en") -> list[dict]:
    """Vision-model text recognition. Returns raw line dicts; mapping lines onto
    regulated declarations stays with the deterministic extraction layer.
    """
    content = chat(
        model=settings.nebius_vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": READ_LABEL_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_data_url(image_path)}},
                ],
            }
        ],
        temperature=0.0,
        max_tokens=4000,
        json_object=True,
    )
    parsed = parse_json_response(content)
    return parsed.get("lines", [])


def explain_violation(violation: dict, found_value: str | None, lang: str = "en") -> str:
    language_note = (
        "Reply in Hindi (Devanagari script)." if lang == "hi" else "Reply in English."
    )
    finding = (
        f"Value read from the package: {found_value!r}"
        if found_value
        else "The declaration was not found on the package at all."
    )
    return chat(
        messages=[
            {"role": "system", "content": f"{EXPLAIN_PROMPT}\n{language_note}"},
            {
                "role": "user",
                "content": (
                    f"Rule: {violation['clause']} — {violation['title']}\n"
                    f"System finding: {violation['message']}\n"
                    f"{finding}"
                ),
            },
        ],
        temperature=0.2,
        max_tokens=300,
    ).strip()
