"""
Translate a plain-English scheduling request into a valid config file
for cli.py -- e.g. "10-team IPL season, CSK is defending champion, keep
road trips under 3 games" becomes the same JSON that
configs/example_ipl_calendar.json contains.

This is a translation layer, not a scheduling algorithm: it doesn't
touch the actual constraint-solving logic in constrained_scheduler.py
or the optimizers at all. Some LLM turns a natural language description
into JSON, then that JSON gets validated against the EXACT same schema
the CLI already enforces (config_loader.parse_config) before ever being
written to disk -- so a bad or malformed model response fails loudly
with a clear error, rather than silently producing a config that
crashes cli.py later or (worse) runs with unintended settings.

Two backends:
  --backend claude  (default) -- uses the Anthropic API. Requires the
                     ANTHROPIC_API_KEY environment variable.
  --backend ollama   -- runs entirely locally via a running Ollama
                     server. No API key, no cost, no external network
                     call. Needs a model pulled first (see
                     DEFAULT_OLLAMA_MODEL below).

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 nl_to_config.py "10-team IPL season, CSK is defending champion" --output config.json
    python3 cli.py --config config.json --output schedule.json

    # or, fully local:
    ollama pull qwen2.5:7b-instruct
    python3 nl_to_config.py "10-team IPL season, CSK is defending champion" --output config.json --backend ollama
"""

import argparse
import json
import os
import re
import sys

import requests

from config_loader import parse_config


API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5"  # stable alias; see
# https://docs.claude.com/en/docs/about-claude/models/model-ids-and-versions
# if you want to pin a specific model instead.

OLLAMA_DEFAULT_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"  # good structured-output
# performance for its size; llama3.1:8b or mistral:7b are reasonable
# alternatives if you already have one pulled. Larger (14B+) will do
# better if your GPU has the VRAM for it.

SYSTEM_PROMPT = """You translate a plain-English sports scheduling request into a JSON \
config file for a tournament scheduler. Respond with ONLY the JSON object -- no \
markdown fences, no explanation, no preamble.

The config has FOUR possible modes. Pick the one that best matches the request.

--- mode: "round_robin" ---
Flat "everyone plays everyone" schedule.
{
  "mode": "round_robin",
  "teams": ["Team A", "Team B", ...],
  "double_round": true,
  "constraints": {"season_days": 60, "max_consecutive_away": 2, "max_consecutive_home": 3, "min_rest_days": 1},
  "optimize": false
}

--- mode: "weighted" ---
Teams have a conference and division; matchup count depends on relationship.
{
  "mode": "weighted",
  "teams": [{"name": "Team A", "conference": "West", "division": "Pacific"}, ...],
  "rules": {"same_division_games": 4, "same_conference_games": 3, "cross_conference_games": 2},
  "constraints": {"season_days": 90, "max_consecutive_away": 2, "max_consecutive_home": 3, "min_rest_days": 1},
  "optimize": true,
  "optimizer_iterations": 6000,
  "cities": {"Team A": [lat, lon], ...}
}

--- mode: "ipl" ---
The real IPL format: 10 teams in two groups of five. Each team plays its own
group twice, one "row rival" in the other group twice, everyone else once.
{
  "mode": "ipl",
  "group_a": ["Team1", "Team2", "Team3", "Team4", "Team5"],
  "group_b": ["Team6", "Team7", "Team8", "Team9", "Team10"],
  "row_pairs": {"Team1": "Team6", "Team2": "Team7", "Team3": "Team8", "Team4": "Team9", "Team5": "Team10"},
  "constraints": {"season_days": 60, "max_consecutive_away": 2, "max_consecutive_home": 3, "min_rest_days": 1},
  "optimize": true,
  "optimizer_iterations": 6000,
  "cities": {"Team1": [lat, lon], ...}
}

--- mode: "ipl_calendar" ---
Same IPL format as above, PLUS a realistic broadcast calendar: opening day is a
single evening match (ideally the defending champion at home), Saturdays are
double-headers early in the season and taper to single evening games later,
Sundays are always double-headers, weekdays never are, and rest is enforced in
real hours.
{
  "mode": "ipl_calendar",
  "group_a": [...5 teams...],
  "group_b": [...5 teams...],
  "row_pairs": {...},
  "constraints": {"max_consecutive_away": 2, "max_consecutive_home": 3},
  "calendar": {"season_days": 70, "opening_weekday": "Saturday", "min_rest_hours": 48, "defending_champion": "Team1"},
  "optimize": true,
  "optimizer_iterations": 4000,
  "cities": {"Team1": [lat, lon], ...}
}

Rules for filling in the JSON:
- If the request mentions "IPL", real IPL team names, or a "defending champion" /
  "opening day" / "double-header", use "ipl_calendar" mode.
- If it says "IPL format" without calendar/opening-day details, use "ipl" mode.
- If it mentions conferences/divisions (NBA-style), use "weighted" mode.
- Otherwise, default to "round_robin" mode.
- For "ipl"/"ipl_calendar" modes, group_a and group_b MUST have exactly 5 team
  names each -- invent plausible team names if the request doesn't name real ones.
- Only include "cities" if you have genuinely plausible city coordinates for
  every team; otherwise omit it entirely and set "optimize": false.
- Fill in any constraint the request doesn't specify with a sensible default
  (matching the examples above).

DEFAULTS if the request leaves something unspecified -- never leave a
required field empty, always produce a complete, valid config:
- round_robin: if team count/names aren't given, default to 6 teams named
  "Team A".."Team F". double_round defaults true. season_days defaults 60.
- weighted: if team count/names aren't given, default to 8 teams matching the
  example above (2 conferences x 2 divisions x 2 teams). rules default to
  4/3/2 (same_division/same_conference/cross_conference).
- ipl / ipl_calendar: if fewer than 10 team names are given, invent enough
  additional plausible ones to reach exactly 5+5. row_pairs can be omitted
  entirely if not specified -- it defaults to pairing by position automatically.
- ipl_calendar specifically: if the request does NOT name a defending
  champion, DO NOT GUESS ONE -- simply omit "defending_champion" from the
  "calendar" object entirely (or set it to null). A downstream step picks a
  deterministic default if it's missing, so leaving it out is the correct
  and expected behavior, not an error.
- Every mode: max_consecutive_away defaults 2, max_consecutive_home defaults
  3, min_rest_days defaults 1 (or min_rest_hours defaults 48 for
  ipl_calendar).
"""


def _strip_markdown_fences(text: str) -> str:
    """Defensive cleanup: models sometimes wrap JSON in ```json fences
    even when told not to. Strip them if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _call_claude(description: str, model: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. Get a key at "
            "https://console.anthropic.com/ and run:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...   (Mac/Linux)\n"
            "  $env:ANTHROPIC_API_KEY='sk-ant-...'    (Windows PowerShell)"
        )

    response = requests.post(
        API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 2000,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": description}],
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    text_blocks = [b["text"] for b in data["content"] if b.get("type") == "text"]
    return "".join(text_blocks)


def _call_ollama(description: str, model: str, host: str = OLLAMA_DEFAULT_HOST) -> str:
    url = f"{host}/api/chat"
    try:
        response = requests.post(
            url,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": description},
                ],
                "stream": False,
                # Low temperature -- this is structured JSON generation
                # against a fixed schema, not creative writing, so we
                # want the model to stick closely to the format shown
                # in the prompt rather than improvise.
                "options": {"temperature": 0.1},
            },
            timeout=120,  # local generation on consumer GPUs can be
            # noticeably slower than a hosted API, especially on a
            # first call before the model is warm in VRAM
        )
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Couldn't connect to Ollama at {host} -- is it running? "
            "Start it with `ollama serve` (or just open the Ollama app), and make "
            f"sure the model is pulled: `ollama pull {model}`"
        )

    if response.status_code == 404:
        raise RuntimeError(
            f"Ollama doesn't have model '{model}' pulled. Run: ollama pull {model}"
        )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def _call_model(description: str, backend: str, model: str, ollama_host: str) -> str:
    if backend == "claude":
        return _call_claude(description, model)
    if backend == "ollama":
        return _call_ollama(description, model, host=ollama_host)
    raise ValueError(f"Unknown backend '{backend}' -- must be 'claude' or 'ollama'.")


def _apply_missing_field_defaults(raw: dict) -> tuple:
    """
    Deterministic, code-level fallback for fields the model was told to
    leave out rather than guess -- currently just defending_champion for
    ipl_calendar mode. This exists because relying on the LLM to
    remember a "pick something simple" instruction is fragile, especially
    for smaller local models where a buried prompt instruction can get
    dropped. Doing it in Python guarantees the behavior regardless of
    which backend or model produced the response.

    Returns (possibly-modified raw config, list of human-readable notes
    describing what got defaulted, if anything) so the caller can show
    the user what happened rather than silently picking a team for them.
    """
    notes = []

    if raw.get("mode") == "ipl_calendar":
        calendar = raw.setdefault("calendar", {})
        if not calendar.get("defending_champion"):
            group_a = raw.get("group_a") or []
            if group_a:
                default_champion = group_a[0]
                calendar["defending_champion"] = default_champion
                notes.append(
                    f"No defending champion specified -- defaulted to "
                    f"'{default_champion}' (first team in group_a)."
                )

    return raw, notes


def translate(
    description: str,
    backend: str = "claude",
    model: str = None,
    ollama_host: str = OLLAMA_DEFAULT_HOST,
) -> tuple:
    """Translate a natural-language description into a validated config
    dict. Raises ValueError if the model's output doesn't parse as JSON
    or doesn't pass config_loader's validation. Works identically
    regardless of backend -- the validation step doesn't care which LLM
    produced the JSON, only whether it's correct.

    Returns (config dict, list of notes) -- notes describes any
    deterministic default that got applied on top of what the model
    produced (see _apply_missing_field_defaults), so the caller can
    surface that to the user instead of it happening invisibly."""
    if model is None:
        model = DEFAULT_CLAUDE_MODEL if backend == "claude" else DEFAULT_OLLAMA_MODEL

    raw_text = _call_model(description, backend, model, ollama_host)
    cleaned = _strip_markdown_fences(raw_text)

    try:
        raw_config = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Model response wasn't valid JSON: {e}\n\nRaw response:\n{raw_text}"
        )

    raw_config, notes = _apply_missing_field_defaults(raw_config)

    try:
        parse_config(raw_config)  # validates; raises if malformed
    except (ValueError, KeyError) as e:
        raise ValueError(
            f"Model produced JSON, but it failed config validation: {e}\n\n"
            f"Generated config:\n{json.dumps(raw_config, indent=2)}"
        )

    return raw_config, notes


def main():
    parser = argparse.ArgumentParser(description="Translate a plain-English request into a scheduler config.")
    parser.add_argument("description", help="Natural-language description of the schedule you want")
    parser.add_argument("--output", required=True, help="Path to write the resulting config JSON")
    parser.add_argument(
        "--backend", choices=["claude", "ollama"], default="claude",
        help="'claude' uses the Anthropic API (needs ANTHROPIC_API_KEY); "
             "'ollama' runs entirely locally via a running Ollama server (default: claude)"
    )
    parser.add_argument(
        "--model", default=None,
        help=f"Model to use. Default: {DEFAULT_CLAUDE_MODEL} for claude backend, "
             f"{DEFAULT_OLLAMA_MODEL} for ollama backend."
    )
    parser.add_argument(
        "--ollama-host", default=OLLAMA_DEFAULT_HOST,
        help=f"Ollama server address (default: {OLLAMA_DEFAULT_HOST} -- change this "
             "if Ollama is running on a different machine or port)"
    )
    args = parser.parse_args()

    print(f"Sending request to {args.backend}...")
    try:
        config, notes = translate(
            args.description, backend=args.backend, model=args.model, ollama_host=args.ollama_host
        )
    except (RuntimeError, ValueError) as e:
        print(f"Failed: {e}")
        sys.exit(1)

    for note in notes:
        print(f"Note: {note}")

    with open(args.output, "w") as f:
        json.dump(config, f, indent=2)

    print(f"Wrote a valid '{config['mode']}' config to {args.output}")
    print(f"Run it with: python3 cli.py --config {args.output} --output schedule.json")


if __name__ == "__main__":
    main()
