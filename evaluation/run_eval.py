"""run_eval.py — Stage 7 orchestrator.

Evaluation framework (PRD FR-8, TDR Section 4 Stage 7): runs the
labeled Q&A eval set through the full pipeline (Stages 5-6 — retrieval
+ generation; Stages 1-4 are a prerequisite, not run here, since the
sample documents are already ingested/embedded) and reports two
SEPARATE, explicitly labeled metrics per the user's explicit request:

  1. Retrieval accuracy — deterministic, no LLM judgment. For EACH
     requested doc_id, did that document's own expected page appear
     among the chunks actually retrieved FOR THAT SAME doc_id? (Not
     a single pooled expected_page across a whole multi_doc
     question — different documents can have the same clause on
     different pages, so each doc_id is checked against its own
     ground-truth page; see EvalQuestion's expected_pages_by_doc
     field comment.) This measures
     retrieval.pipeline.retrieve_and_rerank() (Stage 5) in isolation,
     BEFORE generation ever runs — so a wrong final answer caused by
     bad generation/citation logic does not get blamed on retrieval,
     and vice versa.
  2. Answer correctness — LLM-graded (Gemini, via evaluation/
     llm_judge.py), using a fixed 3-value verdict scale (correct /
     partially_correct / incorrect) rather than free-text judgment,
     so every result is directly comparable and summarizable across
     the whole run.

Both metrics are broken down by mode (single_doc / multi_doc / legal).

DEVIATION FROM TDR (see TDR.md Section 4's Stage 7 module description,
"via RAGAS metrics: faithfulness, answer relevancy, context
precision"): this implementation uses the custom deterministic
retrieval check + custom LLM-as-judge verdict scale described above
instead of RAGAS, per the user's explicit Stage 7 request (a fixed,
comparable verdict scale with full per-question transcripts for manual
spot-checking, rather than RAGAS's continuous faithfulness/relevancy
scores). RAGAS remains listed in requirements.txt and is not removed —
this is a scope decision for THIS evaluation script, not a decision
to drop RAGAS from the project; revisit if RAGAS's continuous scoring
is wanted alongside or instead of this verdict scale later.

DATASET SOURCES:
  - data/eval/cuad_sample_eval.json — the original 17-question eval
    set (TDR Section 9). Every entry in this file is mode="legal" (see
    evaluation/eval_dataset_supplement.json's docstring-equivalent
    note below for why a supplement was needed).
  - evaluation/eval_dataset_supplement.json — NEW, added alongside
    this script rather than editing the original eval JSON. The
    original file has zero single_doc or multi_doc entries, which
    would leave those two rows of the mode-breakdown table entirely
    empty. Adds 3 single_doc + 3 multi_doc questions with real
    expected_answer/expected_page, each REUSED from already-verified
    Stage 6 manual testing (their answers were independently checked
    against the original source PDFs during Stage 6, not newly
    invented for this file) — see each entry's clause_category for
    which Stage 6 test case it traces back to.
  - evaluation/multi_doc_queries.json — NEW, a SEPARATE 12-query set
    (exceeds the requested 10+) with no expected_answer/expected_page
    at all, used ONLY for the multi-doc coverage stress test below
    (task 3 of the user's request) — a deterministic check of which
    requested documents actually appear in the retrieved chunks,
    directly measuring the coverage gap flagged in TDR Section 2f,
    not an answer-correctness question.

Run from the project root:
    python -m evaluation.run_eval

Makes real Gemini API calls. Per eval question: one query-embedding
call (inside retrieval), one generation call, one grading call. Per
multi-doc coverage query: one query-embedding call. Note that the
coverage stress test is NOT Gemini-free — an earlier version of this
docstring and of estimate_call_count() both wrongly claimed it was,
on the assumption that retrieve_and_rerank() is purely local. It is
not: the reranker is local, but the query embedding it retrieves
with is a Gemini call. See estimate_call_count() for the full
breakdown, and note the floor-vs-actual caveat there about retries.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import List, Literal, Optional, TypedDict

from embedding.embed_chunks import EmbeddingUnavailableError
from evaluation.llm_judge import grade_answer
from generation.answer_with_citations import generate_answer
from generation.gemini_key_rotation import AllModelsAndKeysExhaustedError
from retrieval.pipeline import retrieve_and_rerank

# Verdict recorded when a question could not be graded at all because
# an infrastructure failure prevented the answer from ever being
# produced. Deliberately OUTSIDE the fixed 3-value grading scale
# (correct / partially_correct / incorrect): those three are judgments
# about an answer that exists, and an infra failure produced no answer
# to judge. Scoring one as "incorrect" — which this script previously
# did — silently understates answer quality by counting a Gemini
# outage as a wrong answer, and makes the headline accuracy number
# depend on Google's capacity rather than on the pipeline. Unmeasured
# questions are excluded from both accuracy rates and reported as
# their own explicit count instead.
VERDICT_NOT_MEASURED = "not_measured"

Mode = Literal["single_doc", "multi_doc", "legal"]

_EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_EVAL_PATH = os.path.join(
    os.path.dirname(_EVAL_DIR), "data", "eval", "cuad_sample_eval.json"
)
SUPPLEMENT_EVAL_PATH = os.path.join(_EVAL_DIR, "eval_dataset_supplement.json")
MULTI_DOC_QUERIES_PATH = os.path.join(_EVAL_DIR, "multi_doc_queries.json")
RESULTS_DIR = os.path.join(_EVAL_DIR, "results")

RETRIEVAL_TOP_K = 5  # Matches retrieval.reranker.DEFAULT_TOP_K — the
# same top-K a real query would actually receive, so "did the expected
# page appear in the top-K" measures what a user would really see.

# FIXED BUG (found via a live eval run that hung indefinitely with
# zero visible output for 15+ minutes — see generation/
# gemini_key_rotation.py's GEMINI_REQUEST_TIMEOUT_MS note for the root
# cause): even after fixing the actual hang (no Gemini call had an
# explicit network timeout), a legitimately slow run (waiting through
# several keys' worth of 503 backoff, for example) would still LOOK
# identical to a hang from the outside, if this script prints nothing
# until the very end. Per explicit user requirement — "I want a
# progress check-in at intervals... If a single call is going to
# retry for longer than [threshold], that should be visible, not
# indistinguishable from a total freeze" — main() now prints one
# timestamped, flushed line after EVERY question (not just every 5),
# and explicitly flags any single question whose total time (Stage 5
# retrieval + Stage 6 generation + grading, combined) exceeds this
# threshold, so a genuinely slow-but-progressing run is visibly
# different from a silent freeze.
SLOW_QUESTION_WARNING_SECONDS = 120


class EvalQuestion(TypedDict):
    doc_ids: List[str]  # Normalized: always a list, even for a
    # single-doc_id entry (the original eval JSON uses a singular
    # "doc_id" string key; the supplement's multi_doc entries use a
    # "doc_ids" list — both are normalized to this one shape by
    # _load_eval_questions() below, so the rest of this module never
    # has to branch on which key was present in the source file).
    mode: Mode
    clause_category: str
    question: str
    expected_answer: str
    expected_pages_by_doc: dict  # {doc_id: expected_page_int}.
    # SCHEMA CHANGE (found via user's manual review of the multi_doc
    # supplement entries — a real, confirmed page-number bug, not
    # just a design nitpick): a single-doc/legal entry has exactly
    # one doc_id, so a single expected_page int was fine for those 17
    # + 3 entries. But a multi_doc entry compares MULTIPLE documents,
    # each with its OWN, independently-verified page number for the
    # clause in question (e.g. a "governing law" clause can genuinely
    # sit on page 4 of one contract and page 3 of another — confirmed
    # against the raw PDF page count for both documents involved,
    # independent of any embedded footer digit AND independent of
    # this pipeline's own stored page_num metadata, since ground
    # truth must not be derived from the thing being evaluated or the
    # eval becomes circular). A single int could not represent this
    # correctly for a multi_doc entry — it would silently score every
    # OTHER document's page as "wrong" whenever they didn't happen to
    # share a page number with whichever one document the single int
    # matched. Every entry now uses this per-doc dict shape uniformly
    # (a single-doc/legal entry from the original 17-question file is
    # normalized into a one-entry dict by _normalize_entry() below),
    # so downstream code (check_retrieval_accuracy) has exactly one
    # shape to handle regardless of mode.


class QuestionRecord(TypedDict):
    """One fully-graded eval question — the full per-question
    transcript the user explicitly asked for ("I need the full
    transcript, not just a pass/fail count").
    """

    doc_ids: List[str]
    mode: Mode
    clause_category: str
    question: str
    expected_answer: str
    expected_pages_by_doc: dict  # See EvalQuestion's field comment.
    retrieved_pages_by_doc: dict  # {doc_id: [page_num, ...]} — every
    # page_num actually retrieved for EACH requested doc_id
    # separately (not merged across docs), in rank order — kept even
    # for a doc_id whose expected page didn't show up, so a spot-check
    # can see exactly what WAS retrieved for that specific document,
    # not just a pass/fail bit for the whole question.
    retrieval_correct_by_doc: dict  # {doc_id: bool} — whether THAT
    # doc_id's own expected page appeared among its own retrieved
    # pages. A multi_doc question is only fully retrieval_correct if
    # every requested doc_id's own expected page was found — see
    # retrieval_correct below.
    retrieval_correct: bool  # True iff retrieval_correct_by_doc is
    # True for every requested doc_id (all(...), not any(...) — a
    # multi_doc question where only ONE of several documents' pages
    # was actually retrieved is NOT a full retrieval success).
    generated_answer: str
    generation_warning: Optional[str]
    generation_provider: Optional[str]  # which answer provider served
    # the generation call (env var name, e.g. "RAG_Groq"), or None if
    # no LLM call was made. Added with TDR Section 2i: with seven
    # vendors rotating, the provider is the unit that cooldowns and
    # session-removal act on, so a result cannot be interpreted — or
    # a bad streak attributed — without it.
    generation_model: Optional[str]  # which model actually produced
    # the answer, as reported by the provider's own response rather
    # than the configured id (they differ for the openrouter/free
    # alias, which routes to an arbitrary free model per request).
    # Required so every logged result names its model.
    verdict: str
    verdict_reason: str
    grading_provider: Optional[str]  # same, for the grading call —
    # kept separate because generation and grading can legitimately
    # land on different providers for the same question, and a verdict
    # needs to be attributable to whoever actually issued it.
    grading_model: Optional[str]
    grading_raw_response: str
    error: Optional[str]  # populated instead of the above fields if
    # this question raised an exception, so one failure doesn't crash
    # the whole run (see run_eval_suite's per-question try/except).
    error_kind: Optional[str]  # None on success, else one of:
    #   "all_models_and_keys_exhausted" — every allowed generation/
    #       grading model failed on every configured key (429/503/
    #       timeout). Infrastructure, not a code defect.
    #   "embedding_unavailable" — the Stage 5 retrieval query
    #       embedding could not be produced (also infrastructure; see
    #       embedding.embed_chunks.EmbeddingUnavailableError).
    #   "other" — anything else, i.e. a genuine bug worth fixing.
    # ADDED per explicit user requirement: a bare error string made
    # a Gemini outage indistinguishable from a KeyError in our own
    # code, even though those demand opposite responses ("wait for
    # capacity" vs "there is a defect"). This field makes the
    # distinction machine-readable in the results JSON rather than
    # something you have to infer by reading error text.
    measured: bool  # False iff this question was never successfully
    # graded, i.e. it contributes to NO accuracy rate. See
    # VERDICT_NOT_MEASURED for why an infra failure must not be
    # counted as an incorrect answer.


class CoverageRecord(TypedDict):
    """One multi-doc coverage stress-test result (task 3 of the user's
    request) — deterministic, no LLM grading involved.
    """

    query_id: str
    question: str
    doc_ids_requested: List[str]
    doc_ids_covered: List[str]  # requested doc_ids that had >=1 chunk
    # actually appear in the retrieved top-K
    doc_ids_missing: List[str]  # requested doc_ids that had ZERO
    # chunks in the retrieved top-K — this is the TDR Section 2f
    # coverage gap, made concrete and countable
    full_coverage: bool  # True iff doc_ids_missing is empty
    error: Optional[str]


def load_eval_questions() -> List[EvalQuestion]:
    """Loads and normalizes both eval sources (original + supplement)
    into one flat list of EvalQuestion.
    """
    questions: List[EvalQuestion] = []

    with open(ORIGINAL_EVAL_PATH, "r", encoding="utf-8") as f:
        for entry in json.load(f):
            questions.append(_normalize_entry(entry))

    with open(SUPPLEMENT_EVAL_PATH, "r", encoding="utf-8") as f:
        for entry in json.load(f):
            questions.append(_normalize_entry(entry))

    return questions


def _normalize_entry(entry: dict) -> EvalQuestion:
    """Normalizes two independent schema variations into one common
    shape, so downstream code never has to branch on which source
    file (or which mode) an entry came from:

      1. A singular "doc_id" string (the original 17-question eval
         JSON's schema, always single_doc/legal) vs. a "doc_ids" list
         (the supplement's multi_doc entries) — normalized to always
         a list.
      2. A singular "expected_page" int (every entry in the original
         17 + the supplement's 3 single_doc/legal entries — exactly
         one doc_id, so exactly one page is unambiguous) vs. a
         "expected_pages_by_doc" dict (the supplement's multi_doc
         entries — see EvalQuestion's field comment for why a single
         int cannot correctly represent this). Normalized to always
         the per-doc dict shape: a single-doc_id entry's one
         "expected_page" becomes a one-entry dict keyed by that same
         doc_id.
    """
    if "doc_ids" in entry:
        doc_ids = list(entry["doc_ids"])
    else:
        doc_ids = [entry["doc_id"]]

    if "expected_pages_by_doc" in entry:
        expected_pages_by_doc = dict(entry["expected_pages_by_doc"])
    else:
        # Exactly one doc_id in this branch (single_doc/legal) — the
        # one "expected_page" int unambiguously belongs to that one
        # doc_id.
        expected_pages_by_doc = {doc_ids[0]: entry["expected_page"]}

    return {
        "doc_ids": doc_ids,
        "mode": entry["mode"],
        "clause_category": entry.get("clause_category", ""),
        "question": entry["question"],
        "expected_answer": entry["expected_answer"],
        "expected_pages_by_doc": expected_pages_by_doc,
    }


def load_multi_doc_queries() -> List[dict]:
    with open(MULTI_DOC_QUERIES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def check_retrieval_accuracy(eval_q: EvalQuestion) -> tuple:
    """Deterministically checks, PER REQUESTED doc_id, whether that
    doc_id's own expected page appears among the actually-retrieved
    chunks belonging to that SAME doc_id. No LLM involved — this is
    Stage 5 in isolation.

    Checked per-doc rather than against one pooled list of every page
    retrieved across all docs — see EvalQuestion's field comment for
    why: a multi_doc question can have different expected pages for
    different documents, so "was ANY expected page found ANYWHERE"
    would be too loose a check (it could pass by finding doc A's page
    while doc B's page never showed up at all, which is exactly the
    TDR Section 2f coverage gap this eval is partly meant to surface,
    not paper over).

    Returns:
        (chunks, retrieved_pages_by_doc, retrieval_correct_by_doc,
        retrieval_correct) — chunks is the actual reranked chunk list
        this retrieval produced, returned so run_question() can pass
        it straight into generate_answer() instead of triggering a
        SECOND, identical retrieval (see run_question's note on the
        duplicate-retrieval fix). retrieved_pages_by_doc keeps every
        page_num actually retrieved for EACH doc_id separately (rank
        order, may contain duplicates), so a spot-check can see
        exactly what came back for that specific document even on a
        miss. retrieval_correct is True only if EVERY requested
        doc_id's own expected page was found among its own retrieved
        pages.
    """
    chunks = retrieve_and_rerank(
        eval_q["question"], eval_q["mode"], eval_q["doc_ids"], top_k=RETRIEVAL_TOP_K
    )

    retrieved_pages_by_doc: dict = {doc_id: [] for doc_id in eval_q["doc_ids"]}
    for c in chunks:
        if c["doc_id"] in retrieved_pages_by_doc:
            retrieved_pages_by_doc[c["doc_id"]].append(c["page_num"])

    retrieval_correct_by_doc = {
        doc_id: expected_page in retrieved_pages_by_doc.get(doc_id, [])
        for doc_id, expected_page in eval_q["expected_pages_by_doc"].items()
    }
    retrieval_correct = all(retrieval_correct_by_doc.values())

    return chunks, retrieved_pages_by_doc, retrieval_correct_by_doc, retrieval_correct


def run_question(eval_q: EvalQuestion) -> QuestionRecord:
    """Runs one eval question through retrieval accuracy (Stage 5,
    deterministic) + full answer generation (Stage 6) + LLM grading,
    building the complete per-question record.
    """
    base: dict = {
        "doc_ids": eval_q["doc_ids"],
        "mode": eval_q["mode"],
        "clause_category": eval_q["clause_category"],
        "question": eval_q["question"],
        "expected_answer": eval_q["expected_answer"],
        "expected_pages_by_doc": eval_q["expected_pages_by_doc"],
    }

    try:
        chunks, retrieved_pages_by_doc, retrieval_correct_by_doc, retrieval_correct = (
            check_retrieval_accuracy(eval_q)
        )

        # FIXED WASTE (found while investigating an incorrect call
        # estimate): this previously called generation.pipeline.
        # answer_question(), which internally runs
        # retrieve_and_rerank() AGAIN for the same question — a second,
        # byte-identical retrieval whose only effect was one extra
        # Gemini embedding call (embed_query) plus a redundant local
        # rerank, per question. check_retrieval_accuracy() above has
        # already produced exactly the chunk list generate_answer()
        # needs, so it is passed through directly. This removes one
        # Gemini call per eval question with no change to what is
        # measured: the chunks the answer is generated from are now
        # provably the SAME chunks the retrieval-accuracy metric was
        # scored against, rather than a separate retrieval that merely
        # should have matched.
        result = generate_answer(
            eval_q["question"], chunks, eval_q["mode"], answer_style="full"
        )
        generated_answer = result["answer"]

        grading = grade_answer(eval_q["question"], generated_answer, eval_q["expected_answer"])

        return {
            **base,
            "retrieved_pages_by_doc": retrieved_pages_by_doc,
            "retrieval_correct_by_doc": retrieval_correct_by_doc,
            "retrieval_correct": retrieval_correct,
            "generated_answer": generated_answer,
            "generation_warning": result["warning"],
            "generation_provider": result.get("provider_used"),
            "generation_model": result.get("model_used"),
            "verdict": grading["verdict"],
            "verdict_reason": grading["reason"],
            "grading_provider": grading.get("provider_used"),
            "grading_model": grading.get("model_used"),
            "grading_raw_response": grading["raw_response"],
            "error": None,
            "error_kind": None,
            "measured": True,
        }

    # FAIL CLEANLY AND DISTINCTLY (explicit user requirement). Three
    # separate branches instead of one blanket `except Exception`,
    # because the three cases mean genuinely different things and the
    # old single branch erased that difference: it recorded every
    # failure as verdict="incorrect" with a bare error string, so a
    # Gemini capacity outage was reported as a wrong answer and was
    # indistinguishable from a defect in our own code.
    except AllModelsAndKeysExhaustedError as exc:
        # Every allowed model on every key is down. The rotation layer
        # has already printed its own bordered banner; this adds the
        # question-level context (which question was lost) so the
        # result is traceable without cross-referencing the log.
        print("", flush=True)
        print("  " + "!" * 84, flush=True)
        print("  !! QUESTION NOT MEASURED — GEMINI TOTAL EXHAUSTION", flush=True)
        print(f"  !! question    : {eval_q['question'][:76]!r}", flush=True)
        print(f"  !! mode        : {eval_q['mode']}", flush=True)
        print(f"  !! model chain : {', '.join(exc.models)}", flush=True)
        print(f"  !! keys swept  : {exc.num_keys}", flush=True)
        print(
            "  !! This question is recorded as not_measured and EXCLUDED from "
            "accuracy",
            flush=True,
        )
        print(
            "  !! rates — it is an infrastructure failure, not a wrong answer.",
            flush=True,
        )
        print("  " + "!" * 84, flush=True)
        print("", flush=True)
        return _unmeasured_record(base, exc, "all_models_and_keys_exhausted")

    except EmbeddingUnavailableError as exc:
        # Stage 5 never got a query vector, so retrieval could not run
        # at all. Also infrastructure — and specifically NOT a
        # retrieval-quality miss, so it must not be scored as one.
        print("", flush=True)
        print("  " + "!" * 84, flush=True)
        print("  !! QUESTION NOT MEASURED — QUERY EMBEDDING UNAVAILABLE", flush=True)
        print(f"  !! question : {eval_q['question'][:76]!r}", flush=True)
        print(f"  !! detail   : {exc}", flush=True)
        print("  " + "!" * 84, flush=True)
        print("", flush=True)
        return _unmeasured_record(base, exc, "embedding_unavailable")

    except Exception as exc:
        # Anything else is a real defect. Kept non-fatal so one bad
        # question doesn't discard the whole run's results, but
        # labeled "other" so it is never confused with a capacity
        # problem.
        print("", flush=True)
        print("  " + "!" * 84, flush=True)
        print(
            "  !! QUESTION NOT MEASURED — UNEXPECTED ERROR (LIKELY A CODE DEFECT)",
            flush=True,
        )
        print(f"  !! question : {eval_q['question'][:76]!r}", flush=True)
        print(f"  !! error    : {type(exc).__name__}: {exc}", flush=True)
        print("  " + "!" * 84, flush=True)
        print("", flush=True)
        return _unmeasured_record(base, exc, "other")


def _unmeasured_record(base: dict, exc: Exception, error_kind: str) -> QuestionRecord:
    """Builds the record for a question that could not be graded.

    retrieval_correct is False here only because nothing was
    retrieved — summarize_by_mode excludes unmeasured questions from
    the retrieval-accuracy denominator entirely, so this False is
    never counted as a retrieval miss.
    """
    return {
        **base,
        "retrieved_pages_by_doc": {},
        "retrieval_correct_by_doc": {},
        "retrieval_correct": False,
        "generated_answer": "",
        "generation_warning": None,
        "generation_provider": None,
        "generation_model": None,
        "verdict": VERDICT_NOT_MEASURED,
        "verdict_reason": f"NOT MEASURED ({error_kind}): {type(exc).__name__}: {exc}",
        "grading_provider": None,
        "grading_model": None,
        "grading_raw_response": "",
        "error": f"{type(exc).__name__}: {exc}",
        "error_kind": error_kind,
        "measured": False,
    }


def run_coverage_check(query: dict) -> CoverageRecord:
    """Runs one multi-doc coverage stress-test query (task 3): the
    coverage judgement is deterministic — no generation, no grading,
    no LLM opinion, just checking which of the requested doc_ids
    actually contributed at least one chunk to the retrieved top-K
    (see TDR Section 2f, the known limitation this directly measures).

    NOT Gemini-free, though: the retrieve_and_rerank() call below
    still costs one Gemini query-embedding call. Calling this function
    "purely deterministic" is what previously led estimate_call_count()
    to wrongly score coverage queries as zero API calls — deterministic
    SCORING does not imply no API usage.
    """
    requested = query["doc_ids"]
    try:
        chunks = retrieve_and_rerank(
            query["question"], "multi_doc", requested, top_k=RETRIEVAL_TOP_K
        )
        covered_set = {c["doc_id"] for c in chunks}
        covered = [d for d in requested if d in covered_set]
        missing = [d for d in requested if d not in covered_set]

        return {
            "query_id": query["query_id"],
            "question": query["question"],
            "doc_ids_requested": requested,
            "doc_ids_covered": covered,
            "doc_ids_missing": missing,
            "full_coverage": len(missing) == 0,
            "error": None,
        }
    except Exception as exc:
        return {
            "query_id": query["query_id"],
            "question": query["question"],
            "doc_ids_requested": requested,
            "doc_ids_covered": [],
            "doc_ids_missing": requested,
            "full_coverage": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def estimate_call_count(num_questions: int, num_coverage_queries: int) -> dict:
    """Returns the estimated Gemini API call breakdown for a full run,
    so the user can sanity-check against quota headroom BEFORE running
    (explicit user requirement).

    FIXED BUG (found mid-live-run, after this function had already
    been used to get sign-off on an inaccurate number): this
    previously counted ONLY generation + grading calls, and asserted
    that the coverage stress test made zero Gemini calls because it
    "only calls retrieve_and_rerank." That was wrong. retrieval.
    pipeline.retrieve_and_rerank() -> retrieval.retriever.retrieve()
    -> embedding.embed_chunks.embed_query() is itself a Gemini API
    call (the query-embedding call, routed through the same
    call_with_key_rotation as everything else — only the reranker
    that runs afterwards is local). So EVERY retrieval, including
    every coverage query, costs one Gemini call. The old estimate
    reported 46 for the current dataset when the real figure was
    roughly 104.

    IMPORTANT — this is a FLOOR, not a ceiling: it counts one call per
    logical operation, i.e. the best case where every call succeeds on
    the first key. Each 429/503/timeout retry inside
    call_with_key_rotation is an additional real HTTP request, so a
    single logical call can cost up to len(get_api_keys()) attempts
    (7, with the current .env). During the Gemini 503 congestion
    observed on 2026-09-24/25, individual generation calls routinely
    consumed all 7 attempts. Treat this number as "calls if nothing
    retries," and expect the true count to be higher whenever the
    per-key rotation log lines show retries.
    """
    # One query-embedding call per retrieval. Each eval question now
    # performs exactly ONE retrieval (see run_question's
    # duplicate-retrieval fix note) and each coverage query performs
    # one.
    question_embedding_calls = num_questions
    coverage_embedding_calls = num_coverage_queries

    generation_calls = num_questions  # one generate_answer() call each
    grading_calls = num_questions  # one grade_answer() call each

    total = (
        question_embedding_calls
        + coverage_embedding_calls
        + generation_calls
        + grading_calls
    )

    # RELABELLED (TDR Section 2i): the TOTAL is unchanged, but the
    # calls no longer all go to Gemini. Embedding calls still use the
    # GEMINI_API_KEY..._7 pool, while generation and grading now go to
    # whichever answer provider is currently active. Reporting all 81
    # under one "Gemini" heading would misstate which quota each call
    # actually consumes — and quota headroom is the whole reason this
    # estimate exists.
    return {
        "eval_questions": num_questions,
        "coverage_queries": num_coverage_queries,
        "[GEMINI keys] question_embedding_calls (retrieval)": question_embedding_calls,
        "[GEMINI keys] coverage_embedding_calls (retrieval)": coverage_embedding_calls,
        "[GEMINI keys] subtotal": question_embedding_calls + coverage_embedding_calls,
        "[ANSWER providers] generation_calls": generation_calls,
        "[ANSWER providers] grading_calls": grading_calls,
        "[ANSWER providers] subtotal": generation_calls + grading_calls,
        "total_estimated_calls (floor, assumes no retries)": total,
    }


def summarize_by_mode(records: List[QuestionRecord]) -> dict:
    """Builds the per-mode breakdown for both metrics (retrieval
    accuracy, answer correctness) — see this module's docstring.
    """
    modes = sorted({r["mode"] for r in records})
    summary = {}

    for mode in modes:
        mode_records = [r for r in records if r["mode"] == mode]
        n = len(mode_records)

        # Rates are computed over MEASURED questions only. A question
        # lost to a Gemini outage is not evidence about retrieval or
        # answer quality in either direction, so including it in the
        # denominator would silently depress both metrics and make the
        # headline numbers a function of Google's capacity on the day
        # of the run. The unmeasured count is reported separately and
        # prominently instead — see VERDICT_NOT_MEASURED.
        measured = [r for r in mode_records if r["measured"]]
        n_measured = len(measured)
        n_unmeasured = n - n_measured

        retrieval_correct_count = sum(1 for r in measured if r["retrieval_correct"])
        verdict_counts = {
            "correct": 0,
            "partially_correct": 0,
            "incorrect": 0,
            VERDICT_NOT_MEASURED: 0,
        }
        for r in mode_records:
            verdict_counts[r["verdict"]] += 1

        error_kind_counts: dict = {}
        for r in mode_records:
            if r["error_kind"]:
                error_kind_counts[r["error_kind"]] = (
                    error_kind_counts.get(r["error_kind"], 0) + 1
                )

        summary[mode] = {
            "num_questions": n,
            "num_measured": n_measured,
            "num_unmeasured": n_unmeasured,
            "retrieval_accuracy": (
                retrieval_correct_count / n_measured if n_measured else None
            ),
            "retrieval_correct_count": retrieval_correct_count,
            "verdict_counts": verdict_counts,
            "answer_correct_rate": (
                verdict_counts["correct"] / n_measured if n_measured else None
            ),
            "error_kind_counts": error_kind_counts,
        }

    return summary


def summarize_coverage(coverage_records: List[CoverageRecord]) -> dict:
    n = len(coverage_records)
    full_coverage_count = sum(1 for r in coverage_records if r["full_coverage"])

    total_requested = sum(len(r["doc_ids_requested"]) for r in coverage_records)
    total_missing = sum(len(r["doc_ids_missing"]) for r in coverage_records)

    return {
        "num_queries": n,
        "full_coverage_count": full_coverage_count,
        "full_coverage_rate": full_coverage_count / n if n else 0.0,
        "total_docs_requested": total_requested,
        "total_docs_missing": total_missing,
        "doc_level_coverage_rate": (
            (total_requested - total_missing) / total_requested if total_requested else 0.0
        ),
    }


def print_summary_report(
    question_records: List[QuestionRecord],
    coverage_records: List[CoverageRecord],
) -> None:
    mode_summary = summarize_by_mode(question_records)
    coverage_summary = summarize_coverage(coverage_records)

    n = len(question_records)
    measured_records = [r for r in question_records if r["measured"]]
    n_measured = len(measured_records)
    unmeasured_records = [r for r in question_records if not r["measured"]]

    overall_retrieval_correct = sum(1 for r in measured_records if r["retrieval_correct"])
    overall_verdict_counts = {
        "correct": 0,
        "partially_correct": 0,
        "incorrect": 0,
        VERDICT_NOT_MEASURED: 0,
    }
    for r in question_records:
        overall_verdict_counts[r["verdict"]] += 1

    print("=" * 88)
    print("STAGE 7 EVALUATION SUMMARY")
    print("=" * 88)
    print(f"\nTotal eval questions: {n}")
    print(f"Successfully measured:  {n_measured}/{n}")

    # Loud, unmissable block when anything went unmeasured — the
    # headline rates below are over MEASURED questions only, so this
    # has to be stated before them, not buried after. Printed only
    # when it applies, so a clean run stays clean.
    if unmeasured_records:
        kind_counts: dict = {}
        for r in unmeasured_records:
            kind_counts[r["error_kind"]] = kind_counts.get(r["error_kind"], 0) + 1

        print("")
        print("!" * 88)
        print(
            f"!! WARNING: {len(unmeasured_records)}/{n} QUESTION(S) COULD NOT BE "
            f"MEASURED AND ARE EXCLUDED"
        )
        print("!! FROM EVERY RATE BELOW. The rates are over measured questions only.")
        print("!!")
        for kind, count in sorted(kind_counts.items()):
            print(f"!!   {kind}: {count}")
        if "all_models_and_keys_exhausted" in kind_counts:
            print("!!")
            print(
                "!! all_models_and_keys_exhausted means every allowed model failed on "
                "every"
            )
            print(
                "!! key (429/503/timeout). This is a Gemini capacity problem, not a "
                "pipeline"
            )
            print(
                "!! defect, and NOT a wrong answer. gemini-3.6-flash was deliberately "
                "NOT"
            )
            print("!! used as a further fallback (it caused the 2026-09-24/25 outage).")
        if "other" in kind_counts:
            print("!!")
            print(
                "!! 'other' indicates an UNEXPECTED error — likely a real code defect. "
                "See"
            )
            print("!! the per-question error detail in the results JSON.")
        print("!" * 88)
        print("")

    if n_measured:
        print(
            f"Overall retrieval accuracy: {overall_retrieval_correct}/{n_measured} "
            f"({overall_retrieval_correct / n_measured * 100:.1f}%) of measured"
        )
        print(
            f"Overall answer correctness — correct: "
            f"{overall_verdict_counts['correct']}/{n_measured} "
            f"({overall_verdict_counts['correct'] / n_measured * 100:.1f}%) | "
            f"partially_correct: {overall_verdict_counts['partially_correct']} | "
            f"incorrect: {overall_verdict_counts['incorrect']} | "
            f"not_measured: {overall_verdict_counts[VERDICT_NOT_MEASURED]}"
        )
    else:
        print("Overall retrieval accuracy: n/a — NO questions were measured.")
        print("Overall answer correctness: n/a — NO questions were measured.")

    print("\n--- Breakdown by mode (rates over measured questions only) ---")
    header = (
        f"{'Mode':<12} {'N':>3} {'Meas':>5} {'Retrieval Acc':>14} "
        f"{'Correct':>9} {'Partial':>9} {'Incorrect':>10} {'Unmeas':>7}"
    )
    print(header)
    print("-" * len(header))
    for mode, s in mode_summary.items():
        retrieval_acc = (
            f"{s['retrieval_accuracy'] * 100:>13.1f}%"
            if s["retrieval_accuracy"] is not None
            else f"{'n/a':>14}"
        )
        print(
            f"{mode:<12} {s['num_questions']:>3} {s['num_measured']:>5} "
            f"{retrieval_acc} "
            f"{s['verdict_counts']['correct']:>9} "
            f"{s['verdict_counts']['partially_correct']:>9} "
            f"{s['verdict_counts']['incorrect']:>10} "
            f"{s['num_unmeasured']:>7}"
        )

    print("\n--- Multi-doc coverage stress test (task 3) ---")
    print(f"Queries run: {coverage_summary['num_queries']}")
    print(
        f"Queries with FULL coverage (every requested doc represented): "
        f"{coverage_summary['full_coverage_count']}/{coverage_summary['num_queries']} "
        f"({coverage_summary['full_coverage_rate'] * 100:.1f}%)"
    )
    print(
        f"Document-level coverage rate (across all requested docs, all queries): "
        f"{coverage_summary['doc_level_coverage_rate'] * 100:.1f}% "
        f"({coverage_summary['total_docs_requested'] - coverage_summary['total_docs_missing']}/"
        f"{coverage_summary['total_docs_requested']} requested docs actually represented)"
    )
    print("\nPer-query detail:")
    for r in coverage_records:
        status = "FULL" if r["full_coverage"] else "GAP"
        print(f"  [{status}] {r['query_id']}: {r['question']}")
        print(f"        requested: {r['doc_ids_requested']}")
        if r["doc_ids_missing"]:
            print(f"        MISSING:   {r['doc_ids_missing']}")
        if r["error"]:
            print(f"        ERROR:     {r['error']}")

    print("\n" + "=" * 88)


def save_results_json(
    question_records: List[QuestionRecord],
    coverage_records: List[CoverageRecord],
) -> str:
    """Writes the full results (every question's full record, per the
    user's explicit "I need the full transcript" requirement) plus
    both summaries to a timestamped JSON file.

    Returns:
        The path the results were written to.
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(RESULTS_DIR, f"eval_results_{timestamp}.json")

    payload = {
        "generated_at_utc": timestamp,
        "summary_by_mode": summarize_by_mode(question_records),
        "coverage_summary": summarize_coverage(coverage_records),
        "question_records": question_records,
        "coverage_records": coverage_records,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return out_path


def main() -> None:
    eval_questions = load_eval_questions()
    coverage_queries = load_multi_doc_queries()

    estimate = estimate_call_count(len(eval_questions), len(coverage_queries))
    print("=" * 88, flush=True)
    print("ESTIMATED API CALL COUNT FOR THIS RUN", flush=True)
    print("(embeddings consume the Gemini key pool; generation and "
          "grading consume answer-provider quota)", flush=True)
    print("=" * 88, flush=True)
    for key, value in estimate.items():
        print(f"  {key}: {value}", flush=True)
    print("=" * 88, flush=True)

    if "--estimate-only" in sys.argv:
        print("\n--estimate-only passed: exiting without making any API calls.", flush=True)
        return

    print(f"\nRunning {len(eval_questions)} eval question(s)...\n", flush=True)
    question_records = []
    run_start = time.monotonic()
    for i, q in enumerate(eval_questions, start=1):
        q_start = time.monotonic()
        record = run_question(q)
        q_elapsed = time.monotonic() - q_start
        question_records.append(record)

        # Status names the error KIND, not just "ERROR", so the
        # one-line-per-question log distinguishes a capacity outage
        # from a code defect at a glance.
        status = "OK" if record["measured"] else f"NOT_MEASURED:{record['error_kind']}"
        slow_flag = (
            f" [SLOW — exceeded {SLOW_QUESTION_WARNING_SECONDS}s threshold]"
            if q_elapsed > SLOW_QUESTION_WARNING_SECONDS
            else ""
        )
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(
            f"[{timestamp}] question {i}/{len(eval_questions)} done in "
            f"{q_elapsed:.1f}s [{status}]{slow_flag} — "
            f"mode={record['mode']} verdict={record['verdict']} "
            f"retrieval_correct={record['retrieval_correct']} "
            f"gen={record.get('generation_provider')}/{record.get('generation_model')} "
            f"grade={record.get('grading_provider')}/{record.get('grading_model')} "
            f"— {record['question'][:70]!r}",
            flush=True,
        )
        if record["error"]:
            print(f"    error detail: {record['error']}", flush=True)

    total_elapsed = time.monotonic() - run_start
    print(
        f"\nAll {len(eval_questions)} eval question(s) done in {total_elapsed:.1f}s "
        f"(avg {total_elapsed / len(eval_questions):.1f}s/question).\n",
        flush=True,
    )

    print(f"Running {len(coverage_queries)} multi-doc coverage query(ies)...\n", flush=True)
    coverage_records = []
    for i, cov_q in enumerate(coverage_queries, start=1):
        cov_start = time.monotonic()
        cov_record = run_coverage_check(cov_q)
        cov_elapsed = time.monotonic() - cov_start
        coverage_records.append(cov_record)

        status = "FULL" if cov_record["full_coverage"] else "GAP"
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(
            f"[{timestamp}] coverage query {i}/{len(coverage_queries)} "
            f"({cov_record['query_id']}) done in {cov_elapsed:.1f}s [{status}]",
            flush=True,
        )

    print_summary_report(question_records, coverage_records)

    out_path = save_results_json(question_records, coverage_records)
    print(f"\nFull results (every question's complete record) saved to: {out_path}")


if __name__ == "__main__":
    main()
