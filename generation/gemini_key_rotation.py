"""gemini_key_rotation.py — shared Gemini client helper (TDR Section 2d).

Provides multi-key rotation for Gemini API calls, so hitting one
project's free-tier daily quota (429 RESOURCE_EXHAUSTED) doesn't stop
the pipeline — the call is retried against the next configured key
before giving up.

Placed in generation/ rather than a new top-level package: this keeps
the change contained to a single new file rather than "spread across
the codebase," per the user's explicit request. All three Gemini call
sites (ingestion/image_analyzer.py — Stage 3, embedding/embed_chunks.py
— Stage 4, generation/answer_with_citations.py — Stage 6) import from
here instead of constructing their own retry logic.

DEVIATION FROM TDR (see TDR.md Section 2d): this is a testing/
development-volume workaround (Gemini's free-tier quota is enforced
per Google Cloud project, not per account, so multiple projects yield
multiple independent quota pools) — NOT a production-scale rate-limit
or load-balancing solution. See Section 2d for full reasoning and
what stays unchanged.
"""

from __future__ import annotations

import os
import time
from typing import Callable, List, TypeVar

from dotenv import load_dotenv
from google.genai import errors as genai_errors

load_dotenv()

T = TypeVar("T")

# Backoff before retrying a 503 UNAVAILABLE against the next key.
# FIXED BUG (found via manual Stage 6 test run, case 5 of 7 — the whole
# run crashed with an unhandled ServerError): 503 "high demand" is a
# server-side capacity issue shared by every request to that model
# globally, not a per-key/per-project problem (confirmed via Gemini's
# own error message — "usually temporary" — and multiple third-party
# reports of this exact error being a known, recurring, model-wide
# overload condition, e.g. https://inventivehq.com/knowledge-base/
# gemini/gemini-503-model-is-overloaded). That means firing all 7
# configured keys at the SAME overloaded backend within milliseconds
# of each other (no delay at all, as this loop originally did) can
# plausibly hit 503 on every single one, exhausting every key in one
# instant sweep and crashing the whole call — which is exactly what
# happened. A 429 (quota) IS genuinely per-project, so rotating keys
# immediately (no delay) is the right move there; a 503 needs a beat
# of real wall-clock time to have a chance of hitting a
# less-congested backend instance, which key rotation alone does not
# provide. This constant is only used for the 503 case — a 429 still
# rotates immediately, unchanged from before.
#
# WIDENED (found via three separate live Stage 6 test runs the same
# night: case 5 crashed the run once, then case 3 failed twice in a
# row across two full re-runs, then case 5 failed again on a third
# re-run) — a short, linearly-growing 2s/4s/6s.../12s backoff (42s
# swept across all 7 keys) was not enough; different cases kept
# failing on ALL 7 keys across multiple independent runs, meaning the
# sweep was still finishing faster than the congestion window was
# clearing. Every third-party report of this error recommends waiting
# on the order of minutes, not seconds, so the backoff is now
# exponential (10s, 20s, 40s, 80s, ...) with a cap, giving a real
# multi-minute window across a full 7-key sweep before giving up
# entirely, instead of retrying so fast it barely differs from no
# backoff at all.
_UNAVAILABLE_RETRY_BACKOFF_BASE_SECONDS = 10.0
_UNAVAILABLE_RETRY_BACKOFF_MAX_SECONDS = 60.0

# Reads GEMINI_API_KEY, then GEMINI_API_KEY_2 .. GEMINI_API_KEY_7, in
# that order, skipping any that aren't set. At least GEMINI_API_KEY
# must be present (enforced by the caller, same as before this
# change) — the _2..._7 keys are optional extras.
_KEY_ENV_VARS = ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(2, 8)]


def get_api_keys() -> List[str]:
    """Returns every configured Gemini API key, in rotation order.

    TEMPORARY DEBUG OVERRIDE: if GEMINI_DISABLE_ROTATION is set to any
    truthy value, only GEMINI_API_KEY is returned, ignoring
    GEMINI_API_KEY_2..._7 entirely. Added to isolate/verify the Stage
    6 citation-parsing fix against a live LLM response using only the
    original (known-working) key, while the newer keys' "no longer
    available to new users" model-access issue is investigated
    separately — see TDR Section 2d discussion. Not meant to be a
    permanent setting; unset GEMINI_DISABLE_ROTATION (or leave it
    unset) to restore full rotation once the new-key issue is
    resolved.
    """
    if os.getenv("GEMINI_DISABLE_ROTATION"):
        only_key = os.getenv("GEMINI_API_KEY")
        return [only_key] if only_key else []

    keys = []
    for var_name in _KEY_ENV_VARS:
        value = os.getenv(var_name)
        if value:
            keys.append(value)
    return keys


def call_with_key_rotation(make_call: Callable[[str], T]) -> T:
    """Calls `make_call(api_key)` — a function accepting one API key
    and returning a result — retrying with the next configured key
    each time the call fails with a 429 RESOURCE_EXHAUSTED (quota) or
    503 UNAVAILABLE (transient server overload) error.

    FIXED BUG #1 (found via live Stage 6 test after the
    gemini-3.6-flash model change, TDR Section 2e): originally only
    caught genai_errors.ClientError (4xx), so a 503 UNAVAILABLE —
    which the SDK raises as a separate genai_errors.ServerError (5xx),
    not a ClientError — was never caught here at all and propagated
    immediately on the first key, without ever trying another key.
    A 503 ("this model is currently experiencing high demand") is not
    tied to which key/project sent the request, so retrying with a
    different key has a reasonable chance of hitting a
    less-congested backend instance and succeeding — the same
    "worth rotating" reasoning as a 429, so both are now handled the
    same way. Only a genuine 4xx request problem (bad request, model
    not found for this key, etc.) still raises immediately, since a
    different key would hit the identical problem.

    FIXED BUG #2 (found via the very next live Stage 6 test run,
    case 5 of 7 — the whole run still crashed even with #1 fixed):
    a 503 is a server-side capacity issue shared across ALL keys
    hitting that model, not a per-key problem — so firing through
    every configured key with no delay at all can hit 503 on every
    single one within milliseconds, exhausting all of them in one
    instant sweep. Fixed by adding a sleep between key attempts
    specifically on the 503 branch (see
    _UNAVAILABLE_RETRY_BACKOFF_BASE_SECONDS) — giving Google's
    backend a beat of wall-clock time to shed the "high demand"
    spike between attempts, which is what every third-party report
    of this error recommends. A 429 still rotates with no delay,
    since that reasoning does not apply to a per-project quota
    error.

    WIDENED (found via two more live test runs the same night: a
    short 2s/4s/6s.../12s linear backoff still let every key get
    exhausted by 503 on two DIFFERENT cases across two separate
    re-runs) — the backoff is now exponential and capped (10s, 20s,
    40s, 60s, 60s, ...), giving a multi-minute window across a full
    7-key sweep instead of the ~42 seconds the linear version gave,
    since every third-party report of this error says the
    congestion window is measured in minutes, not seconds.

    Args:
        make_call: a function that takes an api_key string and
            performs one Gemini API call (constructing its own
            genai.Client(api_key=...) internally), returning the
            result. Any call site (vision, embedding, generation)
            can pass its own closure here.

    Returns:
        Whatever make_call returns, from whichever key succeeded
        first.

    Raises:
        RuntimeError: if no API keys are configured at all.
        The last exception encountered: if every configured key was
            exhausted/unavailable (429/503) or failed for some other
            reason on the final key tried.
    """
    keys = get_api_keys()
    if not keys:
        raise RuntimeError(
            "No GEMINI_API_KEY (or GEMINI_API_KEY_2..._7) found. Add "
            "at least GEMINI_API_KEY to a .env file in the project "
            "root (see env.example)."
        )

    last_exception: Exception = None  # type: ignore[assignment]

    for attempt, key in enumerate(keys):
        try:
            return make_call(key)
        except genai_errors.ClientError as exc:
            if _is_quota_exhausted(exc):
                last_exception = exc
                continue  # Try the next key immediately — 429 is a
                # per-project quota problem, so a different key's
                # quota pool is unaffected; no benefit in waiting.
            raise  # A non-quota 4xx (bad request, model not found for
            # this key, etc.) — don't mask it by retrying with a
            # different key; the request itself is the problem, not
            # which key sent it.
        except genai_errors.ServerError as exc:
            if _is_transiently_unavailable(exc):
                last_exception = exc
                # Exponential, capped backoff before trying the next
                # key — see _UNAVAILABLE_RETRY_BACKOFF_BASE_SECONDS
                # note above for why this needs to be minutes, not
                # seconds, for a 503 specifically. Skipped after the
                # last key, since there's nothing left to retry into.
                if attempt < len(keys) - 1:
                    delay = min(
                        _UNAVAILABLE_RETRY_BACKOFF_BASE_SECONDS * (2**attempt),
                        _UNAVAILABLE_RETRY_BACKOFF_MAX_SECONDS,
                    )
                    time.sleep(delay)
                continue
            raise  # Some other 5xx we don't specifically recognize —
            # surface it rather than silently exhausting every key on
            # an error rotating won't fix.

    # Every key was tried and every one hit a quota/availability error.
    raise last_exception


def _is_quota_exhausted(exc: genai_errors.ClientError) -> bool:
    """Returns True if this ClientError is specifically a 429
    RESOURCE_EXHAUSTED quota error (as opposed to some other 4xx,
    e.g. an invalid request, which rotating keys would not fix).

    Confirmed against the installed google-genai SDK source
    (google.genai.errors.APIError): the HTTP status code is exposed
    as the `.code` int attribute (not `.status_code`, which exists
    only as a local variable inside the SDK's own raise_for_response,
    never on the exception instance itself).
    """
    return exc.code == 429


def _is_transiently_unavailable(exc: genai_errors.ServerError) -> bool:
    """Returns True if this ServerError is a 503 UNAVAILABLE (transient
    high-demand/overload), as opposed to some other 5xx.
    """
    return exc.code == 503
