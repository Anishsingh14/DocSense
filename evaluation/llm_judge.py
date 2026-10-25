"""llm_judge.py — Stage 7 module.

LLM-as-judge grading for answer correctness (PRD FR-8 / TDR Section 4
Stage 7: "reports... answer correctness"). Compares a generated answer
against a labeled expected_answer and returns one of a fixed,
comparable verdict set — never free-text judgment — plus a one-line
reasoning string, per the user's explicit requirement: "a clear,
consistent verdict scale... not free-text judgment, so results are
comparable and summarizable."

No existing LLM-call helper was reusable for this (generation/
confidence_check.py is pure heuristic, no LLM call — see TDR Section 4
Stage 6 module list). This follows the same call-construction pattern
as the one existing Gemini call site precedent, generation/
answer_with_citations.py's _call_llm: a _make_call(api_key) closure
passed into generation.gemini_key_rotation.call_with_key_rotation, so
grading calls get the same 429/503 multi-key resilience (TDR Sections
2d/2e) as every other Gemini call in this codebase, with no separate
setup needed.
"""

from __future__ import annotations

import re
from typing import Literal, TypedDict

from generation.provider_rotation import call_with_provider_rotation

# CHANGED (TDR Section 2i): grading previously reused Stage 6's Gemini
# GENERATION_MODELS chain. Both now share the multi-provider rotation
# in generation/provider_rotation.py instead, which keeps the original
# rationale intact — grading is a text-only task of the same
# complexity class as answer generation, so a healthy provider should
# benefit both paths — while removing the single-vendor shared-fate
# problem that left 5 of 11 Stage 7 questions unmeasured on
# 2026-10-06. The per-provider model is pinned in
# provider_rotation.PROVIDERS; there is no separate grading model list
# to keep in sync any more.

Verdict = Literal["correct", "partially_correct", "incorrect"]

_VALID_VERDICTS = {"correct", "partially_correct", "incorrect"}

# Anchors the model to emit a single machine-parseable line first,
# then its reasoning — parsed by _parse_grading_response below. Kept
# to exactly 3 verdicts (not a free-text judgment) so every graded
# result is directly comparable/summarizable across the whole eval
# run, per the user's explicit requirement.
_GRADING_PROMPT_TEMPLATE = """You are grading whether a generated answer is factually correct, using a labeled expected answer as ground truth.

Question: {question}

Expected answer (ground truth): {expected_answer}

Generated answer (to grade): {generated_answer}

Grade the generated answer against the expected answer, allowing for reasonable wording variation, paraphrasing, or additional correct detail — the generated answer does not need to match word-for-word to be correct. Judge substantive factual agreement only.

Respond with EXACTLY two lines, in this exact format, and nothing else:
VERDICT: <correct|partially_correct|incorrect>
REASON: <one sentence explaining the verdict>

Verdict definitions:
- correct: the generated answer conveys the same substantive facts as the expected answer (wording may differ).
- partially_correct: the generated answer is factually consistent with the expected answer but is incomplete, missing a material part of it, or only partially addresses the question.
- incorrect: the generated answer contradicts the expected answer, states the information was not found when the expected answer shows it should have been, or is substantively wrong/unrelated.
"""


class GradingResult(TypedDict):
    verdict: Verdict
    reason: str
    raw_response: str
    provider_used: str  # which answer provider graded this (env var
    # name, e.g. "RAG_Groq"). Recorded because a verdict is only
    # interpretable if you know who issued it — different vendors
    # grade with noticeably different strictness, so a spot-check
    # needs to be able to group verdicts by grader.
    model_used: str  # the model that actually served the grading
    # call, as reported by the provider itself (differs from the
    # configured id for the openrouter/free alias).


def grade_answer(question: str, generated_answer: str, expected_answer: str) -> GradingResult:
    """Grades a generated answer against a labeled expected answer.

    Args:
        question: the original eval question.
        generated_answer: the answer produced by generation.pipeline.
            answer_question() (the "answer" field of its AnswerResult).
        expected_answer: the labeled ground-truth answer from the eval
            dataset.

    Returns:
        GradingResult with a fixed-set verdict ("correct" |
        "partially_correct" | "incorrect"), a one-line reason, and the
        raw model response (kept for the full-transcript logging the
        user asked for, in case the parsed fields ever need auditing
        against exactly what the grader said).
    """
    prompt = _GRADING_PROMPT_TEMPLATE.format(
        question=question,
        expected_answer=expected_answer,
        generated_answer=generated_answer,
    )
    raw_response, provider_used, model_used = _call_llm(prompt)
    verdict, reason = _parse_grading_response(raw_response)

    return {
        "verdict": verdict,
        "reason": reason,
        "raw_response": raw_response,
        "provider_used": provider_used,
        "model_used": model_used,
    }


def _parse_grading_response(raw_response: str) -> tuple:
    """Parses the grader's VERDICT/REASON lines into a validated
    verdict and reason string.

    Deliberately defensive rather than assuming the model followed
    the exact format perfectly every time (the same lesson learned
    the hard way across Stage 6's citation-parsing bugs, TDR Section
    2f-adjacent): searches for the VERDICT/REASON labels anywhere in
    the response rather than requiring them on specific line numbers,
    and falls back to "incorrect" with an explicit parse-failure
    reason (rather than silently mis-scoring, or crashing the whole
    eval run) if the expected labels aren't found at all.
    """
    verdict_match = re.search(
        r"VERDICT:\s*(correct|partially_correct|incorrect)", raw_response, re.IGNORECASE
    )
    reason_match = re.search(r"REASON:\s*(.+)", raw_response, re.IGNORECASE)

    if not verdict_match:
        return (
            "incorrect",
            f"GRADING PARSE FAILURE: could not find a valid VERDICT line in the "
            f"grader's response; defaulting to 'incorrect' rather than silently "
            f"mis-scoring. Raw response was: {raw_response!r}",
        )

    verdict = verdict_match.group(1).lower()
    if verdict not in _VALID_VERDICTS:
        # Should be unreachable given the regex above only matches the
        # 3 valid values, but kept as an explicit guard rather than
        # trusting the regex alone — see TDR's general "never trust
        # LLM output blindly" principle (Section 6).
        verdict = "incorrect"

    reason = reason_match.group(1).strip() if reason_match else "(grader did not provide a REASON line)"

    return verdict, reason


def _call_llm(prompt: str) -> tuple:
    """Sends the grading prompt to the current answer provider.

    Returns:
        (raw_response_text, provider_used, model_used). Same
        call-construction pattern as generation/
        answer_with_citations.py's _call_llm — see module docstring.
    """
    return call_with_provider_rotation(
        [{"role": "user", "content": prompt}]
    )
