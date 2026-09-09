#!/usr/bin/env python
"""
Reconcile app/agents/constants.py MODELS against each provider's live model
list, and report any catalog id the provider no longer serves.

WHY THIS EXISTS
---------------
A stale model id is not a cosmetic problem -- it is a hard 404 on the user's
turn, and the only signal is a failed session. This app shipped two at once:
`gemini-2.0-flash` ("no longer available") and `llama-3.3-70b-versatile`
(deprecated by Groq in June 2026). Both had been flagged in a comment as
"verify these someday", which is not a mechanism.

Run it on a schedule (CI cron, or before a release) so the catalog's decay is
discovered by you rather than by a user mid-session:

    python scripts/verify_model_catalog.py

Exit codes: 0 = every id a provider could be checked against is live.
            1 = at least one catalog id is missing from its provider's list.
            2 = could not check anything (no keys configured at all).

Keys are read the same way the app reads them (app.core.config Settings,
which loads backend/.env), so this sees whatever the running app sees --
no separate export step. A provider with no key is reported as SKIPPED,
never as a failure: a missing local key says nothing about whether the
model still exists.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.constants import MODELS  # noqa: E402
from app.core.config import get_settings  # noqa: E402

TIMEOUT = 30.0


async def _anthropic(client: httpx.AsyncClient, key: str) -> set[str]:
    ids: set[str] = set()
    url = "https://api.anthropic.com/v1/models?limit=100"
    while url:
        r = await client.get(url, headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        body = r.json()
        ids.update(m["id"] for m in body.get("data", []))
        # The Models API paginates; a single page can hide the exact id we care about.
        after = body.get("last_id") if body.get("has_more") else None
        url = f"https://api.anthropic.com/v1/models?limit=100&after_id={after}" if after else None
    return ids


async def _openai_compatible(client: httpx.AsyncClient, key: str, base: str) -> set[str]:
    r = await client.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    return {m["id"] for m in r.json().get("data", [])}


async def _gemini(client: httpx.AsyncClient, key: str) -> set[str]:
    ids: set[str] = set()
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=200"
    while url:
        r = await client.get(url)
        r.raise_for_status()
        body = r.json()
        # Gemini returns "models/gemini-3.6-flash"; the catalog stores the bare id.
        ids.update(m["name"].removeprefix("models/") for m in body.get("models", []))
        token = body.get("nextPageToken")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models"
            f"?key={key}&pageSize=200&pageToken={token}"
        ) if token else None
    return ids


#: provider -> (Settings attribute holding the platform key, coroutine
#: returning that provider's live model ids)
PROVIDERS = {
    "anthropic": ("anthropic_api_key", _anthropic),
    "openai": ("openai_api_key", lambda c, k: _openai_compatible(c, k, "https://api.openai.com/v1")),
    "groq": ("groq_api_key", lambda c, k: _openai_compatible(c, k, "https://api.groq.com/openai/v1")),
    "gemini": ("gemini_api_key", _gemini),
}


_DATED_SUFFIX = re.compile(r"-\d{8}$")


def _resolve(model_id: str, live: set[str]) -> str | None:
    """
    Return the live id backing `model_id`, or None if the provider no longer
    serves it.

    Exact match first. Failing that, accept an undated alias of a dated live
    id: Anthropic's /v1/models lists older models under their canonical dated
    slug (`claude-haiku-4-5-20251001`) while the undated alias
    (`claude-haiku-4-5`) remains the correct thing to send in a request.
    Without this the checker cries wolf on a perfectly valid id -- and a
    checker that reports false alarms gets ignored, which defeats the point.

    The suffix must look like a date (-YYYYMMDD) so this can't quietly match
    a genuinely different model that merely shares a prefix.
    """
    if model_id in live:
        return model_id
    dated = [l for l in live if _DATED_SUFFIX.sub("", l) == model_id and l != model_id]
    return max(dated) if dated else None  # newest snapshot, if several


async def main() -> int:
    # "nexus" is the virtual auto-pick model with no provider of its own.
    wanted: dict[str, set[str]] = {}
    for model in MODELS:
        if model["provider"] != "nexus":
            wanted.setdefault(model["provider"], set()).add(model["id"])

    stale: list[str] = []
    checked_any = False
    settings = get_settings()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for provider, ids in sorted(wanted.items()):
            attr, fetch = PROVIDERS[provider]
            key = getattr(settings, attr, None) or os.environ.get(attr.upper())
            if not key:
                print(f"SKIP  {provider:10s} no {attr.upper()} configured; cannot verify {len(ids)} id(s)")
                continue

            try:
                live = await fetch(client, key)
            except Exception as exc:  # noqa: BLE001 -- report and keep checking the others
                print(f"ERROR {provider:10s} could not list models: {exc}")
                continue

            checked_any = True
            for model_id in sorted(ids):
                match = _resolve(model_id, live)
                if match == model_id:
                    print(f"ok    {provider:10s} {model_id}")
                elif match:
                    print(f"ok    {provider:10s} {model_id}  (alias of {match})")
                else:
                    print(f"STALE {provider:10s} {model_id}  <-- not in provider's model list")
                    stale.append(f"{provider}:{model_id}")

    if not checked_any:
        print("\nNo provider could be checked -- set at least one provider API key.")
        return 2
    if stale:
        print(f"\n{len(stale)} stale catalog entr{'y' if len(stale) == 1 else 'ies'}: {', '.join(stale)}")
        print("Update MODELS in app/agents/constants.py (and the frontend fallback in")
        print("frontend/src/lib/nexus/constants.ts) before these 404 on a user's turn.")
        return 1

    print("\nCatalog is current for every provider that could be checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
