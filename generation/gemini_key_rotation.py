"""gemini_key_rotation.py — shared Gemini client helper (TDR Section 2d).

This module provides multi-key rotation for Gemini API calls, so hitting one
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
what stays unchanged respectively.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Callable, List, Optional, Tuple, TypeVar

import httpx
from dotenv import load_dotenv
from google.genai import errors as genai_errors
from google.genai import types as genai_types

load_dotenv()

T = TypeVar("T")


class AllModelsAndKeysExhaustedError(RuntimeError):
    """Raised by call_with_model_and_key_rotation when EVERY allowed
    model has failed on EVERY configured key with a retryable error
    (429 / 503 / network timeout).

    WHY THIS EXISTS AS A DISTINCT TYPE (explicit user requirement):
    previously this path just re-raised the last underlying
    genai_errors.ServerError, which made total infrastructure
    exhaustion indistinguishable — in both the log and the recorded
    eval result — from an ordinary bug in our own code (a KeyError,
    a TypeError, a bad chunk shape). Those two things demand opposite
    responses: one means "wait for Google capacity, the code is
    fine," the other means "there is a defect to fix." Collapsing
    them into one generic error string is the same silent-degradation
    pattern that the embedding fallback fix removed, so exhaustion now
    has its own type, its own loud banner, and its own recorded
    error_kind in the eval results.

    This is deliberately NOT raised by call_with_key_rotation (the
    single-model path used by Stage 3 vision and Stage 4 embedding):
    embedding/embed_chunks.py already catches genai_errors.APIError
    and RuntimeError there and converts them into its own
    EmbeddingUnavailableError with backend-specific guidance, and
    this class subclasses RuntimeError — so raising it there would be
    swallowed by that handler and reported under its "no API keys are
    configured at all" message, which would be actively misleading.
    Keeping it to the model+key path leaves both failure modes
    separately identifiable.

    Attributes:
        models: the model chain that was attempted, in priority order.
        num_keys: how many keys were swept.
        last_exception: the final underlying error, also chained via
            `raise ... from`.
    """

    def __init__(
        self,
        models: List[str],
        num_keys: int,
        last_exception: Exception,
    ) -> None:
        self.models = list(models)
        self.num_keys = num_keys
        self.last_exception = last_exception
        super().__init__(
            f"All {num_keys} API key(s) x {len(models)} allowed model(s) "
            f"({', '.join(models)}) failed with retryable errors. Last error: "
            f"{type(last_exception).__name__}: {last_exception}"
        )


# How often _sleep_with_heartbeat emits a "still waiting" line.
_HEARTBEAT_INTERVAL_SECONDS = 15.0

# FIXED BUG (found via a live Stage 7 eval run that hung indefinitely,
# with zero progress for 15+ minutes on the very first question, and
# with no exception ever raised for call_with_key_rotation to catch):
# none of the 4 genai.Client(...) construction sites anywhere in this
# codebase passed an explicit http_options.timeout. Confirmed by
# reading the installed google-genai SDK's own source
# (google.genai._api_client): get_timeout_in_seconds() returns None
# when HttpOptions.timeout is unset, and a separate retry-config code
# path explicitly substitutes the literal string 'inf' (infinity) as
# the timeout whenever self._http_options.timeout is None — this is
# not a guess or an inferred side effect, it is what the SDK's own
# code does by design when no timeout is configured. That value flows
# unchanged into every underlying httpx/aiohttp request call. So if a
# single request hangs on the network side (dropped connection, a
# server that accepts the connection but never responds, etc.) rather
# than cleanly failing with an HTTP error, there was NO code path in
# this SDK that would ever raise an exception — the whole sequential
# eval run froze because the one function everything was waiting on,
# make_call(key), never returned and never raised anything for this
# rotation loop to catch.
#
# 45 seconds — a deliberate, finite bound instead of the SDK's own
# 'inf' default. Tonight's actual failure mode was an INDEFINITE
# wait (15+ minutes with zero resolution), not a call that was
# merely somewhat slow — so any finite value is already a decisive
# improvement over what caused the incident, and this does not need
# to be precisely tuned against real call-latency data to fix that
# specific problem. If a legitimately slow-but-healthy call starts
# getting falsely killed at 45s in practice, revisit with real
# observed latency data at that point rather than now.
GEMINI_REQUEST_TIMEOUT_MS = 45_000


def _ts() -> str:
    """Wall-clock HH:MM:SS stamp for log lines.

    OBSERVABILITY FIX: previously only run_eval.py's per-question
    completion lines carried a timestamp, so the [gemini] rotation
    lines in between were un-timestamped. That made "is this
    progressing or hung?" impossible to answer from the log alone —
    it depended entirely on repeatedly re-reading the file and
    comparing, which is exactly the fragile method that produced a
    false stall report on 2026-09-25 (cached reads looked identical
    to a frozen process). With a stamp on every line, elapsed gaps
    are readable directly off the log.
    """
    return datetime.now().strftime("%H:%M:%S")


def _sleep_with_heartbeat(total_seconds: float, reason: str) -> None:
    """Sleeps, emitting a heartbeat line periodically.

    OBSERVABILITY FIX: a bare time.sleep(60) emits nothing for a full
    minute, which is indistinguishable from a hang when read from the
    outside. This makes deliberate waiting visibly different from
    being stuck — the single most useful signal during the Gemini 503
    congestion, where most wall-clock time was spent in backoff
    sleeps rather than in flight.
    """
    remaining = total_seconds
    while remaining > 0:
        chunk = min(_HEARTBEAT_INTERVAL_SECONDS, remaining)
        time.sleep(chunk)
        remaining -= chunk
        if remaining > 0:
            print(
                f"  [{_ts()}] [gemini] ...still waiting ({reason}), "
                f"{remaining:.0f}s remaining",
                flush=True,
            )


def build_http_options() -> genai_types.HttpOptions:
    """Returns the shared HttpOptions every genai.Client(...)
    construction in this codebase should pass, so a network-level
    hang on ANY Gemini call (vision, embedding, generation, grading)
    fails with a catchable exception instead of blocking forever —
    see GEMINI_REQUEST_TIMEOUT_MS above for why this is needed.

    Usage at each call site:
        client = genai.Client(api_key=api_key, http_options=build_http_options())
    """
    return genai_types.HttpOptions(timeout=GEMINI_REQUEST_TIMEOUT_MS)

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

    PROGRESS LOGGING ADDED (user requirement after a Stage 7 eval run
    stalled with no visible activity for 7+ minutes, and it was not
    possible to distinguish "still legitimately rotating through
    keys" from "genuinely frozen" without a Task Manager CPU/network
    check outside this process entirely): every key attempt now
    prints a line when it starts, and every branch below (success,
    429 rotate, 503 rotate-with-backoff, timeout rotate, non-
    retryable raise, all-keys-exhausted) prints its own outcome line
    with elapsed time — so real-time progress through rotation is
    visible as it happens. The reliable stall signal is now genuine
    TOTAL SILENCE (no lines at all) for several minutes, not elapsed
    time on any single call, since legitimate multi-key rotation,
    local model loading, and Gemini's own generation latency can all
    genuinely take a while without anything being wrong.

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
        key_label = f"key {attempt + 1}/{len(keys)} (...{key[-4:]})"
        call_start = time.monotonic()
        # FEATURE ADDED (user requirement after a live eval run's
        # silence made it impossible to tell "still working through
        # keys" apart from "genuinely frozen"): a line here, and on
        # every rotation/success/final-failure branch below, so the
        # process's real-time progress through key rotation is
        # visible as it happens — total silence for several minutes
        # (no lines at all appearing) becomes the actual stall signal,
        # instead of elapsed time alone (which a legitimate multi-key
        # rotation, model loading, or Gemini's own model "thinking"
        # time can easily exceed without anything being wrong).
        print(f"  [{_ts()}] [gemini] trying {key_label}...", flush=True)
        try:
            result = make_call(key)
            elapsed = time.monotonic() - call_start
            print(
                f"  [{_ts()}] [gemini] {key_label} succeeded in {elapsed:.1f}s",
                flush=True,
            )
            return result
        except genai_errors.ClientError as exc:
            elapsed = time.monotonic() - call_start
            if _is_quota_exhausted(exc):
                last_exception = exc
                print(
                    f"  [{_ts()}] [gemini] {key_label} hit 429 quota exhausted after "
                    f"{elapsed:.1f}s — rotating to next key immediately",
                    flush=True,
                )
                continue  # Try the next key immediately — 429 is a
                # per-project quota problem, so a different key's
                # quota pool is unaffected; no benefit in waiting.
            print(
                f"  [{_ts()}] [gemini] {key_label} hit a non-quota 4xx after "
                f"{elapsed:.1f}s — NOT rotating, raising immediately: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            raise  # A non-quota 4xx (bad request, model not found for
            # this key, etc.) — don't mask it by retrying with a
            # different key; the request itself is the problem, not
            # which key sent it.
        except genai_errors.ServerError as exc:
            elapsed = time.monotonic() - call_start
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
                    print(
                        f"  [{_ts()}] [gemini] {key_label} hit transient {exc.code} after "
                        f"{elapsed:.1f}s — waiting {delay:.0f}s before rotating "
                        f"to next key",
                        flush=True,
                    )
                    _sleep_with_heartbeat(delay, reason=f"503 backoff after {key_label}")
                else:
                    print(
                        f"  [{_ts()}] [gemini] {key_label} hit transient {exc.code} after "
                        f"{elapsed:.1f}s — no keys left to rotate to",
                        flush=True,
                    )
                continue
            print(
                f"  [{_ts()}] [gemini] {key_label} hit an unrecognized 5xx after "
                f"{elapsed:.1f}s — NOT rotating, raising immediately: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            raise  # Some other 5xx we don't specifically recognize —
            # surface it rather than silently exhausting every key on
            # an error rotating won't fix.
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            # FIXED BUG (see GEMINI_REQUEST_TIMEOUT_MS note above): a
            # network-level timeout or connection failure is raised by
            # httpx directly, NOT wrapped into genai_errors.ClientError
            # or ServerError — confirmed by reading google.genai.errors'
            # module contents, which defines no timeout-specific error
            # class at all. Without this except clause, a timeout
            # (now that one is actually configured, instead of the
            # SDK's own 'inf' default) would propagate straight past
            # every clause above and crash the whole calling script on
            # the FIRST key that ever timed out, rather than rotating
            # to the next one. No backoff sleep here (unlike the 503
            # branch) — a timeout already means we waited the full
            # GEMINI_REQUEST_TIMEOUT_MS, so there is no reason to make
            # the next key wait even longer before trying; a different
            # key's connection to Google's backend is not likely to be
            # affected by whatever caused THIS key's request to hang.
            elapsed = time.monotonic() - call_start
            last_exception = exc
            print(
                f"  [{_ts()}] [gemini] {key_label} timed out/failed to connect after "
                f"{elapsed:.1f}s ({type(exc).__name__}) — rotating to next key",
                flush=True,
            )
            continue

    # Every key was tried and every one hit a quota/availability/
    # timeout error.
    print(
        f"  [{_ts()}] [gemini] ALL {len(keys)} key(s) exhausted — raising last error: "
        f"{type(last_exception).__name__}: {last_exception}",
        flush=True,
    )
    raise last_exception


def call_with_model_and_key_rotation(
    make_call: Callable[[str, str], T],
    models: List[str],
) -> Tuple[T, str]:
    """Like call_with_key_rotation, but tries MULTIPLE MODELS within
    each key before rotating to the next key — and reports back which
    model actually served the request.

    Priority order is model-major within key-minor:

        for key in keys:
            for model in models:       # <-- all models on THIS key first
                try this (key, model)
            # only now rotate to the next key

    Rationale for that ordering (confirmed empirically on 2026-09-25):
    a 503 "high demand" is a per-MODEL, globally-shared capacity
    condition — it is not tied to which key sent the request, so
    retrying the same model on a different key is close to useless
    (observed: a single generation call 503'd on all 7 keys in
    sequence, taking ~5 minutes to learn nothing). Switching MODEL is
    the move that can actually succeed, and it costs one immediate
    request rather than a multi-minute key sweep. A 429 is
    per-project-per-model quota ("GenerateRequestsPerDayPerProject
    PerModel"), so a different model on the same key has its own
    separate quota pool too — meaning model-switching helps for both
    retryable classes. Key rotation is kept as the outer, slower
    fallback for the case where every model is unavailable on a key.

    Args:
        make_call: function taking (api_key, model) and performing one
            Gemini call, returning the result.
        models: model names in priority order, highest first. Must be
            non-empty.

    Returns:
        (result, model_used) — model_used is the model name that
        actually produced the result, so callers can record which
        model answered (per the requirement that every logged result
        names its model).

    Raises:
        RuntimeError: if no API keys are configured, or models is empty.
        The last retryable exception: if every (key, model) pair was
            exhausted.
    """
    keys = get_api_keys()
    if not keys:
        raise RuntimeError(
            "No GEMINI_API_KEY (or GEMINI_API_KEY_2..._7) found. Add "
            "at least GEMINI_API_KEY to a .env file in the project "
            "root (see env.example)."
        )
    if not models:
        raise RuntimeError("call_with_model_and_key_rotation requires a non-empty models list.")

    last_exception: Exception = None  # type: ignore[assignment]

    for attempt, key in enumerate(keys):
        key_label = f"key {attempt + 1}/{len(keys)} (...{key[-4:]})"
        last_error_was_503 = False

        for model_index, model in enumerate(models):
            label = f"{key_label} model {model_index + 1}/{len(models)} ({model})"
            call_start = time.monotonic()
            print(f"  [{_ts()}] [gemini] trying {label}...", flush=True)

            try:
                result = make_call(key, model)
                elapsed = time.monotonic() - call_start
                print(
                    f"  [{_ts()}] [gemini] {label} SUCCEEDED in {elapsed:.1f}s",
                    flush=True,
                )
                return result, model

            except genai_errors.ClientError as exc:
                elapsed = time.monotonic() - call_start
                if _is_quota_exhausted(exc):
                    last_exception = exc
                    last_error_was_503 = False
                    print(
                        f"  [{_ts()}] [gemini] {label} hit 429 quota exhausted after "
                        f"{elapsed:.1f}s — trying next model on this key",
                        flush=True,
                    )
                    continue
                print(
                    f"  [{_ts()}] [gemini] {label} hit a non-quota 4xx after "
                    f"{elapsed:.1f}s — NOT retrying, raising immediately: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                raise

            except genai_errors.ServerError as exc:
                elapsed = time.monotonic() - call_start
                if _is_transiently_unavailable(exc):
                    last_exception = exc
                    last_error_was_503 = True
                    print(
                        f"  [{_ts()}] [gemini] {label} hit transient {exc.code} after "
                        f"{elapsed:.1f}s — trying next model on this key "
                        f"immediately ({exc.code} is per-model, not per-key)",
                        flush=True,
                    )
                    continue
                print(
                    f"  [{_ts()}] [gemini] {label} hit an unrecognized 5xx after "
                    f"{elapsed:.1f}s — NOT retrying, raising immediately: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
                raise

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                elapsed = time.monotonic() - call_start
                last_exception = exc
                last_error_was_503 = False
                print(
                    f"  [{_ts()}] [gemini] {label} timed out/failed to connect after "
                    f"{elapsed:.1f}s ({type(exc).__name__}) — trying next model "
                    f"on this key",
                    flush=True,
                )
                continue

        # Every model failed on this key. Rotate to the next one.
        if attempt < len(keys) - 1:
            if last_error_was_503:
                delay = min(
                    _UNAVAILABLE_RETRY_BACKOFF_BASE_SECONDS * (2**attempt),
                    _UNAVAILABLE_RETRY_BACKOFF_MAX_SECONDS,
                )
                print(
                    f"  [{_ts()}] [gemini] all {len(models)} model(s) failed on "
                    f"{key_label} — waiting {delay:.0f}s before rotating to next key",
                    flush=True,
                )
                _sleep_with_heartbeat(delay, reason=f"503 backoff after {key_label}")
            else:
                print(
                    f"  [{_ts()}] [gemini] all {len(models)} model(s) failed on "
                    f"{key_label} — rotating to next key immediately",
                    flush=True,
                )
        else:
            print(
                f"  [{_ts()}] [gemini] all {len(models)} model(s) failed on "
                f"{key_label} — no keys left to rotate to",
                flush=True,
            )

    # LOUD, VISUALLY DISTINCT total-exhaustion banner (explicit user
    # requirement). Previously this was a single [gemini] line
    # formatted identically to every routine rotation line, so the
    # single most important event in the log — "every allowed model
    # on every key is down" — scrolled past looking like ordinary
    # progress. It is now a bordered block that cannot be mistaken
    # for a per-key rotation notice, and it names the exact model
    # chain that was allowed, so it is immediately obvious whether a
    # model was excluded on purpose (gemini-3.6-flash is).
    print("", flush=True)
    print("  " + "!" * 84, flush=True)
    print(
        f"  !! [{_ts()}] GEMINI TOTAL EXHAUSTION — ALL {len(keys)} KEY(S) x "
        f"{len(models)} ALLOWED MODEL(S) FAILED",
        flush=True,
    )
    print(f"  !! allowed model chain : {', '.join(models)}", flush=True)
    print(
        f"  !! last underlying error: {type(last_exception).__name__}: {last_exception}",
        flush=True,
    )
    print(
        "  !! NOT falling back to any other model. gemini-3.6-flash is excluded "
        "by design",
        flush=True,
    )
    print(
        "  !! (it caused the 2026-09-24/25 congestion outage) — failing cleanly "
        "instead.",
        flush=True,
    )
    print("  " + "!" * 84, flush=True)
    print("", flush=True)

    raise AllModelsAndKeysExhaustedError(
        models=models,
        num_keys=len(keys),
        last_exception=last_exception,
    ) from last_exception


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


# Server-side status codes treated as transient and therefore worth
# retrying against another model/key.
#
# FIXED BUG (found in the live Stage 7 run of 2026-10-06, question 3
# of 23): this check previously matched ONLY 503, so a 504
# DEADLINE_EXCEEDED ("Deadline expired before operation could
# complete") fell through to the "unrecognized 5xx" branch, which
# raises immediately WITHOUT trying the fallback model or any other
# key. Two independent things went wrong as a result:
#   1. No retry at all. A 504 is a transient server-side timeout —
#      exactly the class of failure this rotation logic exists to
#      absorb — so raising on the first occurrence threw away the
#      remaining 1 model x 7 keys of perfectly good fallback.
#   2. It was then misreported. run_eval classifies anything that
#      isn't AllModelsAndKeysExhaustedError or
#      EmbeddingUnavailableError as error_kind="other", which prints
#      "LIKELY A CODE DEFECT". So a Google-side capacity timeout was
#      logged as a bug in our code — the precise confusion the
#      error_kind split was added to prevent.
#
# 500 INTERNAL is deliberately NOT included. Google documents it as
# retryable, but unlike 503/504 it does not specifically indicate
# capacity or timing, and it can also accompany a genuinely
# malformed request that would fail identically on every model and
# key. Leaving it out keeps it loudly visible as an unrecognized 5xx
# rather than silently absorbed into 7 keys of retries; revisit if a
# real 500 is ever observed in practice.
_TRANSIENT_SERVER_ERROR_CODES = frozenset({503, 504})


def _is_transiently_unavailable(exc: genai_errors.ServerError) -> bool:
    """Returns True if this ServerError is transient (503 UNAVAILABLE
    high-demand/overload, or 504 DEADLINE_EXCEEDED server-side
    timeout) and therefore worth retrying against another model or
    key, as opposed to some other 5xx that rotating would not fix.
    """
    return exc.code in _TRANSIENT_SERVER_ERROR_CODES
