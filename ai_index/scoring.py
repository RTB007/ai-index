"""Score today's AI fantasy index by calling `claude -p`.

We pass the trailing N-day window of indicators and a fixed rubric, and ask Claude
to return a strict JSON object. The prompt is versioned so historical scores can be
re-computed if the rubric changes.
"""
from __future__ import annotations

import json
import re
import subprocess
from typing import Any

PROMPT_VERSION = 1

RUBRIC = """\
You are scoring the "AI fantasy index" — a 0-100 measure of how hot/hyped the AI market currently is.

ANCHOR your final score to these bands:
  0-20  dormant: few AI mentions, stable, no breakouts.
  20-40 normal background activity, slow organic growth.
  40-60 warm: sustained elevated interest, bull-market vibes, not euphoric.
  60-80 hot: FOMO, retail flood, IPO/funding storm, mainstream media saturation.
  80-100 mania: bubble territory, speculative excess, even non-tech people talking about it.

Method:
- Look at LEVEL (absolute values) AND MOMENTUM (last 7 days vs prior 23 days) of each indicator.
- A breakout in one indicator alone is weaker signal than coherent moves across multiple.
- Weight indicators by signal quality: GDELT > Trends > HN > arXiv for retail/general-market heat.
  (arXiv is a research-supply indicator, not demand. Treat as background, not heat.)
- Be honest: if data looks normal, score 30-50. Reserve 70+ for genuine intensity.
"""

OUTPUT_INSTRUCTION = """\
Return ONLY a JSON object on a single line, no prose, no markdown fences, no commentary:
{"score": <int 0-100>, "rationale": "<1-3 short sentences>", "components": {"<indicator_name>": <int 0-100>, ...}}

Use the same indicator_name keys that appear in the INPUT below for components.
"""


def build_prompt(date_iso: str, window: dict[str, list[dict[str, Any]]]) -> str:
    compact = {
        name: [{"date": p["date"], "value": round(p["value"], 3)} for p in series]
        for name, series in window.items()
    }
    return (
        f"DATE: {date_iso}\n\n"
        f"{RUBRIC}\n"
        f"INPUT — trailing window of raw indicators (most recent last):\n"
        f"{json.dumps(compact, indent=2)}\n\n"
        f"{OUTPUT_INSTRUCTION}"
    )


def _extract_json(text: str) -> dict[str, Any]:
    """Find the first JSON object in text and parse it."""
    text = text.strip()
    # Strip markdown fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: greedy brace match.
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError(f"No JSON object found in Claude output: {text[:300]!r}")
    return json.loads(m.group(0))


def call_claude(prompt: str, claude_bin: str = "claude", timeout: int = 300) -> str:
    """Call `claude -p --output-format json` and return the inner result text."""
    proc = subprocess.run(
        [claude_bin, "-p", "--output-format", "json"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI failed (exit {proc.returncode}): {proc.stderr[:500]}"
        )
    envelope = json.loads(proc.stdout)
    result = envelope.get("result")
    if not isinstance(result, str):
        raise RuntimeError(f"unexpected claude envelope: {envelope}")
    return result


def score(
    date_iso: str,
    window: dict[str, list[dict[str, Any]]],
    claude_bin: str = "claude",
) -> dict[str, Any]:
    """Return {'score': int, 'rationale': str, 'components': dict}."""
    if not window:
        raise ValueError("empty indicator window — nothing to score")
    prompt = build_prompt(date_iso, window)
    raw = call_claude(prompt, claude_bin=claude_bin)
    parsed = _extract_json(raw)
    score_val = int(parsed["score"])
    if not 0 <= score_val <= 100:
        raise ValueError(f"score out of range: {score_val}")
    return {
        "score": score_val,
        "rationale": str(parsed.get("rationale", "")),
        "components": parsed.get("components", {}) or {},
    }
