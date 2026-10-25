"""provider_rotation.py — multi-provider rotation for ANSWER calls (TDR Section 2i).

Replaces the Gemini-only model/key chain for the two LLM calls that
produce answers: Stage 6 generation (generation/answer_with_citations.py)
and Stage 7 grading (evaluation/llm_judge.py). Nothing else moves —
embeddings (Stage 4) and image reading (Stage 3) stay on the legacy
GEMINI_API_KEY..._7 pool via gemini_key_rotation.call_with_key_rotation.

WHY THIS EXISTS: the previous design rotated 7 keys across 2 Gemini
models, all of which share Google's Flash-tier capacity. During the
2026-10-06 Stage 7 run that proved insufficient — gemini-3.8-flash and
gemini-3.7-flash returned 503 within seconds of each other on the same
key, repeatedly, and 5 of 11 questions went unmeasured. Rotating across
independent VENDORS removes that shared-fate problem in a way that
rotating keys or sibling models within one vendor cannot.

ALL SEVEN PROVIDERS ARE OpenAI-COMPATIBLE. Verified live on
2026-10-26: every provider below answered GET /models with HTTP 200
and accepts POST /chat/completions in OpenAI request/response shape —
including Cohere (via its /compatibility/v1 endpoint) and Gemini (via
/v1beta/openai). That means ONE httpx call covers all of them and
Cohere needs no special-case adapter, which was not obvious going in.

NO NEW DEPENDENCY: this uses httpx, already present transitively via
google-genai and already imported by gemini_key_rotation.py. The
`openai` and `cohere` SDKs are deliberately NOT added.

SECURITY: keys are read by their exact, case-sensitive env var names
and never logged in full — log lines show at most the last 6
characters.
"""

from __future__ import annotations

import os
import time
from typing import Dict, List, NamedTuple, Optional, Tuple

import httpx
from dotenv import load_dotenv

from generation.gemini_key_rotation import (
    AllModelsAndKeysExhaustedError,
    GEMINI_REQUEST_TIMEOUT_MS,
    _sleep_with_heartbeat,
    _ts,
)

load_dotenv()

# Reuses the Stage 7 timeout decision unchanged (45s) — see
# gemini_key_rotation.GEMINI_REQUEST_TIMEOUT_MS for why a finite bound
# matters and why 45s specifically.
REQUEST_TIMEOUT_SECONDS = GEMINI_REQUEST_TIMEOUT_MS / 1000.0


class ProviderConfig(NamedTuple):
    """One answer provider.

    Attributes:
        env_var: EXACT, case-sensitive name of the key's env var. Windows
            upper-cases os.environ keys and matches case-insensitively,
            so a wrong case silently works here but would break on
            Linux/macOS — hence these must stay verbatim.
        base_url: OpenAI-compatible base; /chat/completions is appended.
        model: the pinned model id.
        enabled: False means never called at all. See
            _log_disabled_providers_once for why each is off.
        disabled_reason: shown once at startup so a skipped provider is
            never silently absent.
    """

    env_var: str
    base_url: str
    model: str
    enabled: bool
    disabled_reason: str = ""


# Order is the user's explicit rotation order: fastest/most reliable
# first (measured 2026-10-26), disabled ones last.
PROVIDERS: List[ProviderConfig] = [
    ProviderConfig(
        "RAG_Groq", "https://api.groq.com/openai/v1",
        "openai/gpt-oss-20b", True,
    ),
    ProviderConfig(
        "RAG_NVIDIA", "https://integrate.api.nvidia.com/v1",
        "minimaxai/minimax-m3.1-flash", True,
    ),
    ProviderConfig(
        "RAG_Cohere", "https://api.cohere.ai/compatibility/v1",
        "command-r-08-2024", True,
    ),
    ProviderConfig(
        "RAG_OpenRouter", "https://openrouter.ai/api/v1",
        # Alias that picks a free model per request. The ACTUAL serving
        # model is read back out of the response body and reported as
        # model_used — see _extract_model_used.
        "openrouter/free", True,
    ),
    ProviderConfig(
        "RAG_Gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
        # Pinned deliberately rather than using the gemini-flash-latest
        # alias, so the model serving our requests never changes under
        # us without a code change. Note this model timed out 4 of 5
        # times during 2026-10-26 verification (Flash-tier congestion),
        # which is why Gemini sits last among the enabled providers.
        "gemini-3.8-flash", True,
    ),
    ProviderConfig(
        "RAG_SiliconFlow", "https://api.siliconflow.com/v1",
        "Qwen/Qwen2.5-7B-Instruct", False,
        "signup credit exhausted — HTTP 402 'account balance is "
        "insufficient' on any real-size prompt (verified 2026-10-26)",
    ),
    ProviderConfig(
        "RAG_OpenCode_Console", "https://opencode.ai/zen/v1",
        "deepseek-v4.1-flash", False,
        "unusable server-side — '-free' models return HTTP 403 "
        "FreeTierError ('can only be used from within OpenCode') and "
        "paid models return HTTP 402 'Insufficient account funds'. "
        "Client-fingerprint proxy workarounds exist but are "
        "deliberately not used (they circumvent provider access "
        "control)",
    ),
]

# --- Cooldown policy -------------------------------------------------
# Length depends on what went wrong, because the errors mean different
# things: a daily quota will not clear in a minute, whereas a capacity
# blip usually does.
_COOLDOWN_QUOTA_SECONDS = 900.0       # 429 — long; quota windows are hours
_COOLDOWN_TRANSIENT_SECONDS = 60.0    # 503/504/timeout/empty — short

# Statuses that mean "this key will never work again this session", so
# retrying only wastes wall-clock time.
# 402 is grouped with 401/403 per explicit user decision: an exhausted
# balance is not going to refill mid-run, so treating it as transient
# would re-attempt a guaranteed failure on every question.
_SESSION_FATAL_STATUSES = {401, 402, 403}

# Treated as "this prompt is too big for THIS provider" — skipped for
# the current question only, with NO cooldown, since the provider is
# perfectly healthy for shorter prompts.
_CONTEXT_OVERFLOW_STATUSES = {413}
_CONTEXT_OVERFLOW_MARKERS = (
    "context length", "context_length", "maximum context", "too long",
    "reduce the length", "max_tokens", "token limit", "input is too large",
)

# Module-level rotation state. The provider is STICKY: once one works
# it keeps serving every subsequent question until it fails, rather
# than round-robining, so a healthy provider is not abandoned and
# answers stay stylistically consistent across a run.
_sticky_index: int = 0
_cooldown_until: Dict[str, float] = {}
_session_removed: Dict[str, str] = {}
_disabled_logged = False


class AllProvidersExhaustedError(AllModelsAndKeysExhaustedError):
    """Every eligible provider failed for this question.

    Subclasses AllModelsAndKeysExhaustedError ON PURPOSE: evaluation/
    run_eval.py already catches that type and records the question as
    not_measured with error_kind="all_models_and_keys_exhausted",
    excluded from accuracy rates rather than scored as a wrong answer.
    Subclassing keeps that behaviour working untouched while letting
    the message name providers instead of Gemini keys.
    """

    def __init__(self, attempted: List[str], last_exception: Exception) -> None:
        super().__init__(
            models=attempted,
            num_keys=len(attempted),
            last_exception=last_exception,
        )
        self.attempted = list(attempted)


class ProviderCallError(RuntimeError):
    """One provider's attempt failed. Internal to the rotation loop."""

    def __init__(self, label: str, kind: str, detail: str) -> None:
        super().__init__(f"{label}: {kind} — {detail}")
        self.label = label
        self.kind = kind
        self.detail = detail


def _log_disabled_providers_once() -> None:
    """Prints one clear line per disabled provider, once per process.

    Explicit user requirement: a provider that is switched off must not
    just silently vanish from the rotation — the log has to say it was
    skipped and why, so a short provider list is never mistaken for a
    bug.
    """
    global _disabled_logged
    if _disabled_logged:
        return
    _disabled_logged = True
    for p in PROVIDERS:
        if not p.enabled:
            print(
                f"  [{_ts()}] [provider] SKIPPED {p.env_var} — disabled "
                f"(enabled=False), no calls will be made. Reason: "
                f"{p.disabled_reason}",
                flush=True,
            )


def _key_for(provider: ProviderConfig) -> Optional[str]:
    raw = os.getenv(provider.env_var)
    return raw.strip() if raw and raw.strip() else None


def _label(provider: ProviderConfig) -> str:
    """Log label. Includes at most the last 6 characters of the key."""
    key = _key_for(provider)
    suffix = f"...{key[-6:]}" if key else "NO KEY"
    return f"{provider.env_var} ({suffix}) [{provider.model}]"


def _is_context_overflow(status: int, body: str) -> bool:
    if status in _CONTEXT_OVERFLOW_STATUSES:
        return True
    if status != 400:
        return False
    low = body.lower()
    return any(marker in low for marker in _CONTEXT_OVERFLOW_MARKERS)


def _extract_model_used(body: dict, provider: ProviderConfig) -> str:
    """Returns the model that ACTUALLY served the response.

    Explicit user requirement for openrouter/free: that id is an alias
    which routes to an arbitrary free model per request, so recording
    the alias would tell us nothing about what produced an answer.
    OpenAI-compatible responses echo the real model in the top-level
    "model" field, so that is preferred over the configured id
    wherever present.
    """
    served = body.get("model")
    if isinstance(served, str) and served.strip():
        return served.strip()
    return provider.model


def _post_chat(
    provider: ProviderConfig,
    key: str,
    messages: List[dict],
    max_tokens: int,
    temperature: float,
) -> Tuple[str, str]:
    """One HTTP attempt. Returns (text, model_used) or raises ProviderCallError."""
    label = _label(provider)
    payload = {
        "model": provider.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        response = httpx.post(
            f"{provider.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise ProviderCallError(label, "transient", f"{type(exc).__name__}: {exc}") from exc

    if response.status_code != 200:
        body = response.text or ""
        status = response.status_code
        if status in _SESSION_FATAL_STATUSES:
            raise ProviderCallError(label, "session_fatal", f"HTTP {status}: {body[:200]}")
        if _is_context_overflow(status, body):
            raise ProviderCallError(label, "context_overflow", f"HTTP {status}: {body[:200]}")
        if status == 429:
            raise ProviderCallError(label, "quota", f"HTTP {status}: {body[:200]}")
        raise ProviderCallError(label, "transient", f"HTTP {status}: {body[:200]}")

    try:
        body = response.json()
        message = body["choices"][0]["message"]
        text = message.get("content") or ""
    except Exception as exc:
        raise ProviderCallError(
            label, "transient", f"unparseable response ({type(exc).__name__}: {exc})"
        ) from exc

    # EMPTY RESPONSE IS A FAILURE (explicit user decision). Observed
    # live: openrouter/free returned HTTP 200 with 0 characters of
    # content after 20.9s on a legal-mode prompt. Accepting that would
    # hand an empty string to the citation parser, which would then
    # report "no valid citations" — indistinguishable from a model
    # that answered badly. It is a provider malfunction, so it moves
    # to the next provider.
    #
    # NOTE the deliberate distinction: this checks for a STRUCTURALLY
    # empty response, not for an answer whose CONTENT is a negative
    # finding. A provider replying "the contract does not state X" is
    # a legitimate, useful answer (Cohere did exactly that on the
    # legal question) and must NOT be treated as a failure — the
    # absence-detection behaviour in TDR 2g depends on such answers
    # surviving.
    if not text.strip():
        raise ProviderCallError(
            label, "transient",
            "HTTP 200 but response content was empty (provider malfunction)",
        )

    return text, _extract_model_used(body, provider)


def _eligible(now: float) -> List[int]:
    """Indices of providers that could be tried right now."""
    out = []
    for i, p in enumerate(PROVIDERS):
        if not p.enabled:
            continue
        if p.env_var in _session_removed:
            continue
        if _key_for(p) is None:
            continue
        if _cooldown_until.get(p.env_var, 0.0) > now:
            continue
        out.append(i)
    return out


def call_with_provider_rotation(
    messages: List[dict],
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> Tuple[str, str, str]:
    """Sends one chat completion, rotating providers on failure.

    Behaviour (per explicit user specification):
      * STICKY: starts at the current provider and keeps using it for
        every subsequent call until it fails.
      * On failure the NEXT provider answers the SAME question from
        scratch, reusing the already-retrieved chunks. There is no
        resuming from partial output — a half-finished answer from a
        dead provider is discarded entirely.
      * Cooldown length depends on the error: 429 long, 503/504/
        timeout/empty short, 401/402/403 removes the provider for the
        whole session with a loud line, prompt-too-long skips it for
        this question only.

    Returns:
        (text, provider_env_var, model_used) — model_used is the model
        that actually served the response, which for openrouter/free
        differs from the configured alias.

    Raises:
        AllProvidersExhaustedError: every eligible provider failed.
            Subclasses AllModelsAndKeysExhaustedError so run_eval
            records the question as not_measured.
        RuntimeError: no provider is configured/enabled at all.
    """
    global _sticky_index

    _log_disabled_providers_once()

    attempted: List[str] = []
    last_exception: Exception = None  # type: ignore[assignment]
    skip_this_question: set = set()

    for _ in range(len(PROVIDERS)):
        now = time.monotonic()
        eligible = [i for i in _eligible(now) if i not in skip_this_question]
        if not eligible:
            break

        # Honour stickiness: prefer the current index if it is
        # eligible, else advance to the next eligible one in order.
        idx = _sticky_index if _sticky_index in eligible else eligible[0]
        provider = PROVIDERS[idx]
        label = _label(provider)
        attempted.append(f"{provider.env_var}:{provider.model}")

        print(f"  [{_ts()}] [provider] trying {label}...", flush=True)
        start = time.monotonic()
        try:
            text, model_used = _post_chat(
                provider, _key_for(provider), messages, max_tokens, temperature
            )
        except ProviderCallError as exc:
            elapsed = time.monotonic() - start
            last_exception = exc

            if exc.kind == "session_fatal":
                _session_removed[provider.env_var] = exc.detail
                print("", flush=True)
                print("  " + "!" * 84, flush=True)
                print(
                    f"  !! [{_ts()}] PROVIDER REMOVED FOR THIS SESSION: "
                    f"{provider.env_var}",
                    flush=True,
                )
                print(f"  !! after {elapsed:.1f}s — {exc.detail}", flush=True)
                print(
                    "  !! A 401/403 means the key is invalid; a 402 means the balance "
                    "is spent.",
                    flush=True,
                )
                print(
                    "  !! Neither resolves mid-run, so this provider will not be "
                    "retried again.",
                    flush=True,
                )
                print("  " + "!" * 84, flush=True)
                print("", flush=True)

            elif exc.kind == "context_overflow":
                skip_this_question.add(idx)
                print(
                    f"  [{_ts()}] [provider] {label} rejected this prompt as too "
                    f"long after {elapsed:.1f}s — skipping it for THIS question "
                    f"only (no cooldown; it is healthy for shorter prompts)",
                    flush=True,
                )

            elif exc.kind == "quota":
                _cooldown_until[provider.env_var] = now + _COOLDOWN_QUOTA_SECONDS
                print(
                    f"  [{_ts()}] [provider] {label} hit 429 quota after "
                    f"{elapsed:.1f}s — cooling down {_COOLDOWN_QUOTA_SECONDS:.0f}s "
                    f"(quota windows do not clear in seconds)",
                    flush=True,
                )

            else:  # transient
                _cooldown_until[provider.env_var] = now + _COOLDOWN_TRANSIENT_SECONDS
                print(
                    f"  [{_ts()}] [provider] {label} failed transiently after "
                    f"{elapsed:.1f}s — cooling down "
                    f"{_COOLDOWN_TRANSIENT_SECONDS:.0f}s. {exc.detail}",
                    flush=True,
                )

            # Advance stickiness past the failed provider.
            remaining = [i for i in _eligible(time.monotonic()) if i not in skip_this_question]
            _sticky_index = remaining[0] if remaining else 0
            continue

        elapsed = time.monotonic() - start
        _sticky_index = idx  # stay here for subsequent questions
        served_note = (
            f" (alias {provider.model} -> served by {model_used})"
            if model_used != provider.model
            else ""
        )
        print(
            f"  [{_ts()}] [provider] {label} SUCCEEDED in {elapsed:.1f}s"
            f"{served_note}",
            flush=True,
        )
        return text, provider.env_var, model_used

    # Nothing left to try.
    enabled_count = sum(1 for p in PROVIDERS if p.enabled)
    if enabled_count == 0:
        raise RuntimeError(
            "No answer providers are enabled. Set enabled=True for at least one "
            "entry in provider_rotation.PROVIDERS and ensure its key is present "
            "in .env (see .env.example)."
        )
    if not attempted:
        raise RuntimeError(
            "No answer provider was eligible: every enabled provider is either "
            "missing its key, removed for this session (401/402/403), or still "
            "cooling down. Removed: "
            f"{sorted(_session_removed) or 'none'}."
        )

    print("", flush=True)
    print("  " + "!" * 84, flush=True)
    print(
        f"  !! [{_ts()}] ALL ELIGIBLE PROVIDERS FAILED for this question "
        f"({len(attempted)} attempted)",
        flush=True,
    )
    for a in attempted:
        print(f"  !!   tried: {a}", flush=True)
    print(f"  !! last error: {last_exception}", flush=True)
    print(
        "  !! Failing cleanly — no silent fallback to a disabled or "
        "cooled-down provider.",
        flush=True,
    )
    print("  " + "!" * 84, flush=True)
    print("", flush=True)

    raise AllProvidersExhaustedError(attempted, last_exception) from last_exception


def reset_rotation_state_for_tests() -> None:
    """Clears sticky index, cooldowns and session removals.

    Exists so mocked tests can assert each behaviour from a known
    starting point instead of inheriting state from a previous test.
    """
    global _sticky_index, _disabled_logged
    _sticky_index = 0
    _disabled_logged = False
    _cooldown_until.clear()
    _session_removed.clear()
